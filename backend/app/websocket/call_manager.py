import asyncio
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from hmac import compare_digest
from secrets import token_urlsafe
from time import monotonic

from fastapi import WebSocket

from ..config import settings
from ..database import SessionLocal
from ..models.entities import Event
from ..services.command_service import queue_command
from ..services.event_service import create_event, event_to_dict
from ..services.tts_generator_service import generate_tts
from .manager import manager


@dataclass
class PendingCallRequest:
    worker_id: str
    event_id: str
    timeout_task: asyncio.Task


class CallConnectionManager:
    """In-memory relay for 16 kHz mono PCM. Audio is never written to disk."""

    def __init__(self) -> None:
        self.devices: dict[str, list[WebSocket]] = defaultdict(list)
        self.operators: dict[str, list[WebSocket]] = defaultdict(list)
        self.tickets: dict[str, tuple[str, float]] = {}
        self.pending_requests: dict[str, PendingCallRequest] = {}
        self.active_request_events: dict[str, str] = {}
        self.traffic: dict[str, dict[str, int]] = {}
        self.outputs = {}
        self.relay_stats = defaultdict(lambda: {"sent": 0, "dropped": 0, "errors": 0,
            "max_queue": 0, "max_send_ms": 0.0, "max_wait_ms": 0.0, "sent_frames": 0, "sent_bytes": 0, "dropped_bytes": 0, "capacity_drop_bytes": 0, "age_drop_bytes": 0, "control_drop_bytes": 0, "max_enqueue_gap_ms": 0.0})

    async def begin_call_request(self, device_id: str, worker_id: str, event_id: str) -> None:
        if device_id in self.pending_requests:
            await self.cancel_call_request(device_id, reason="replaced")
        task = asyncio.create_task(self._expire_call_request(device_id, event_id))
        self.pending_requests[device_id] = PendingCallRequest(worker_id, event_id, task)

    async def cancel_call_request(
        self,
        device_id: str,
        event_id: str | None = None,
        reason: str = "cancelled",
    ) -> bool:
        pending = self.pending_requests.get(device_id)
        if not pending or (event_id and pending.event_id != event_id):
            return False
        self.pending_requests.pop(device_id, None)
        if pending.timeout_task is not asyncio.current_task():
            pending.timeout_task.cancel()
        await manager.send_device_command(device_id, {"command_type": "stop_call_ringing", "payload": {}})
        event_status = "acknowledged" if reason == "answered" else "resolved"
        if reason == "answered":
            self.active_request_events[device_id] = pending.event_id
        event_data = self._finish_request_event(pending.event_id, reason, event_status)
        if event_data:
            await manager.broadcast("event_status", event_data)
        return True

    async def _expire_call_request(self, device_id: str, event_id: str) -> None:
        try:
            await asyncio.sleep(settings.call_answer_timeout_seconds)
        except asyncio.CancelledError:
            return
        pending = self.pending_requests.get(device_id)
        if not pending or pending.event_id != event_id or self.operators.get(device_id):
            return
        self.pending_requests.pop(device_id, None)
        await manager.send_device_command(device_id, {"command_type": "stop_call_ringing", "payload": {}})

        message = "상대방이 전화를 받지 않습니다."
        audio_path = await generate_tts(message)
        audio_url = f"/tts/{audio_path.name}" if audio_path else None
        command_type = "play_audio" if audio_url else "play_tone"
        command_payload = {
            "message": message,
            "audio_url": audio_url,
            "frequency": 430,
            "duration": 260,
            "purpose": "call_no_answer",
        }
        with SessionLocal() as db:
            original = db.get(Event, event_id)
            if original:
                original.status = "resolved"
                details = json.loads(original.details_json or "{}")
                details["call_state"] = "missed"
                original.details_json = json.dumps(details, ensure_ascii=False)
            missed = create_event(
                db,
                "MISSED_CALL",
                "관리자 부재중 통화",
                "warning",
                pending.worker_id,
                device_id,
                {"original_event_id": event_id, "reason": "no_answer", "timeout_seconds": settings.call_answer_timeout_seconds},
            )
            record = queue_command(db, device_id, command_type, command_payload)
            db.commit()
            missed_data = event_to_dict(missed)
            original_data = event_to_dict(original) if original else None

        delivered = await manager.send_device_command(
            device_id,
            {"command_id": record.command_id, "command_type": command_type, "payload": command_payload},
        )
        with SessionLocal() as db:
            saved_record = db.get(type(record), record.command_id)
            if saved_record:
                saved_record.status = "delivered" if delivered else "queued"
                db.commit()
        if original_data:
            await manager.broadcast("event_status", original_data)
        await manager.broadcast("missed_call", missed_data)

    @staticmethod
    def _finish_request_event(event_id: str, reason: str, status: str = "resolved") -> dict | None:
        with SessionLocal() as db:
            event = db.get(Event, event_id)
            if not event:
                return None
            event.status = status
            details = json.loads(event.details_json or "{}")
            details["call_state"] = reason
            event.details_json = json.dumps(details, ensure_ascii=False)
            db.commit()
            return event_to_dict(event)

    async def _resolve_active_request(self, device_id: str) -> None:
        event_id = self.active_request_events.pop(device_id, None)
        if not event_id:
            return
        event_data = self._finish_request_event(event_id, "ended")
        if event_data:
            await manager.broadcast("event_status", event_data)

    def issue_ticket(self, device_id: str) -> str:
        token = token_urlsafe(24)
        self.tickets[token] = (device_id, monotonic() + 30.0)
        return token

    def valid_device_token(self, token: str) -> bool:
        expected = settings.call_device_token
        return bool(expected and token and compare_digest(expected, token))

    def consume_ticket(self, device_id: str, token: str) -> bool:
        record = self.tickets.pop(token, None)
        return bool(record and record[0] == device_id and record[1] >= monotonic())

    def device_online(self, device_id: str) -> bool:
        return bool(self.devices.get(device_id))

    async def connect_device(self, device_id: str, token: str, websocket: WebSocket) -> bool:
        await websocket.accept()
        if not self.valid_device_token(token):
            await websocket.send_json({"type": "call_status", "status": "unauthorized"})
            await websocket.close(code=4401)
            return False
        self._start_writer(websocket, device_id, "to_helmet")
        self.devices[device_id].append(websocket)
        if self.operators.get(device_id):
            await self.cancel_call_request(device_id, reason="answered")
            await self._send_text(self.devices[device_id], '{"type":"call_start"}')
            await self._send_text(self.operators[device_id], '{"type":"call_status","status":"connected"}')
        return True

    async def connect_operator(self, device_id: str, token: str, websocket: WebSocket) -> bool:
        await websocket.accept()
        if not self.consume_ticket(device_id, token):
            await websocket.send_json({"type": "call_status", "status": "unauthorized"})
            await websocket.close(code=4401)
            return False
        if self.operators.get(device_id):
            await websocket.send_json({"type": "call_status", "status": "busy"})
            await websocket.close(code=4409)
            return False
        self._start_writer(websocket, device_id, "to_web")
        self.operators[device_id].append(websocket)
        self.traffic[device_id] = {"helmet_packets": 0, "helmet_bytes": 0, "operator_packets": 0, "operator_bytes": 0}
        if self.devices.get(device_id):
            await self.cancel_call_request(device_id, reason="answered")
            await self._send_text(self.devices[device_id], '{"type":"call_start"}')
            await self._send_text([websocket], '{"type":"call_status","status":"connected"}')
        else:
            await self._send_text([websocket], '{"type":"call_status","status":"device_offline"}')
        return True

    async def disconnect_device(self, device_id: str, websocket: WebSocket) -> None:
        await self._stop_writer(websocket)
        self._remove(self.devices, device_id, websocket)
        if not self.devices.get(device_id):
            await self._send_text(self.operators.get(device_id, []), '{"type":"call_status","status":"device_offline"}')

    async def disconnect_operator(self, device_id: str, websocket: WebSocket) -> None:
        await self._stop_writer(websocket)
        self._remove(self.operators, device_id, websocket)
        if not self.operators.get(device_id):
            await self._send_text(self.devices.get(device_id, []), '{"type":"call_stop"}')
            await self._resolve_active_request(device_id)

    async def relay_device_bytes(self, device_id: str, payload: bytes) -> None:
        if not payload or len(payload) > 4096 or len(payload) % 2:
            return
        stats = self.traffic.get(device_id)
        if stats is not None:
            stats["helmet_packets"] += 1
            stats["helmet_bytes"] += len(payload)
        await self._send_bytes(self.operators.get(device_id, []), payload)

    async def relay_operator_bytes(self, device_id: str, payload: bytes) -> None:
        if not payload or len(payload) > 4096 or len(payload) % 2:
            return
        stats = self.traffic.get(device_id)
        if stats is not None:
            stats["operator_packets"] += 1
            stats["operator_bytes"] += len(payload)
        await self._send_bytes(self.devices.get(device_id, []), payload)

    async def end_call(self, device_id: str) -> None:
        await self.cancel_call_request(device_id, reason="cancelled")
        await self._send_text(self.devices.get(device_id, []), '{"type":"call_stop"}')
        await self._send_text(self.operators.get(device_id, []), '{"type":"call_status","status":"ended"}')
        await self._resolve_active_request(device_id)

    @staticmethod
    def _remove(store: dict[str, list[WebSocket]], device_id: str, websocket: WebSocket) -> None:
        sockets = store.get(device_id, [])
        if websocket in sockets:
            sockets.remove(websocket)
        if not sockets:
            store.pop(device_id, None)

    def _start_writer(self, socket, device_id, direction):
        state = {"audio": deque(), "control": deque(), "wake": asyncio.Event(),
                 "key": device_id + ":" + direction, "last_enqueue": None}
        self.outputs[socket] = state
        state["task"] = asyncio.create_task(self._writer(socket, state))

    async def _stop_writer(self, socket):
        state = self.outputs.pop(socket, None)
        if state and state["task"] is not asyncio.current_task():
            state["task"].cancel()
            try:
                await state["task"]
            except asyncio.CancelledError:
                pass

    def diagnostics(self, device_id):
        return {key: dict(value) for key, value in self.relay_stats.items()
                if key.startswith(device_id + ":")}

    async def _writer(self, socket, state):
        stats = self.relay_stats[state["key"]]
        try:
            while True:
                await state["wake"].wait()
                while state["control"] or state["audio"]:
                    control = bool(state["control"])
                    payload, queued = (state["control"] if control else state["audio"]).popleft()
                    now = monotonic()
                    stats["max_wait_ms"] = max(stats["max_wait_ms"], (now - queued) * 1000)
                    if not control and now - queued > 0.2:
                        stats["dropped"] += 1
                        stats["dropped_bytes"] += len(payload)
                        stats["age_drop_bytes"] += len(payload)
                        continue
                    frames = 1
                    if not control:
                        # Coalesce only already queued PCM, with no batching delay.
                        while state["audio"] and len(payload) + len(state["audio"][0][0]) <= 1920:
                            more, queued_more = state["audio"].popleft()
                            if now - queued_more > 0.2:
                                stats["dropped"] += 1
                                stats["dropped_bytes"] += len(more)
                                stats["age_drop_bytes"] += len(more)
                                continue
                            payload += more
                            frames += 1
                    # A slow peer cannot block either input receive loop.
                    async with asyncio.timeout(1.0):
                        if control:
                            await socket.send_text(payload)
                        else:
                            await socket.send_bytes(payload)
                    stats["max_send_ms"] = max(stats["max_send_ms"], (monotonic() - now) * 1000)
                    stats["sent"] += 1
                    if not control:
                        stats["sent_frames"] += frames
                        stats["sent_bytes"] += len(payload)
                state["wake"].clear()
        except asyncio.CancelledError:
            raise
        except Exception:
            stats["errors"] += 1
            try:
                async with asyncio.timeout(1.0):
                    await socket.close(code=1011)
            except Exception:
                pass

    async def _send_bytes(self, sockets: list[WebSocket], payload: bytes) -> None:
        for socket in list(sockets):
            state = self.outputs.get(socket)
            if not state or state["task"].done():
                continue
            queue = state["audio"]
            stats = self.relay_stats[state["key"]]
            # At most 200ms PCM16 at 16kHz, independent of variable frame size.
            while queue and (sum(len(item[0]) for item in queue) + len(payload) > 6400 or len(queue) >= 32):
                old, _ = queue.popleft()
                stats["dropped"] += 1
                stats["dropped_bytes"] += len(old)
                stats["capacity_drop_bytes"] += len(old)
            now = monotonic()
            if state["last_enqueue"] is not None:
                stats["max_enqueue_gap_ms"] = max(stats["max_enqueue_gap_ms"], (now - state["last_enqueue"]) * 1000)
            state["last_enqueue"] = now
            queue.append((payload, now))
            stats["max_queue"] = max(stats["max_queue"], len(queue))
            state["wake"].set()

        # Receive() may return immediately for a TCP burst; give the writer a turn.
        # This yields scheduling only and does not wait for network transmission.
        await asyncio.sleep(0)

    async def _send_text(self, sockets: list[WebSocket], payload: str) -> None:
        for socket in list(sockets):
            state = self.outputs.get(socket)
            if not state or state["task"].done():
                continue
            stats = self.relay_stats[state["key"]]
            stats["control_drop_bytes"] += sum(len(item[0]) for item in state["audio"])
            state["audio"].clear()  # Explicitly account for call transition flushing.
            if len(state["control"]) >= 8:
                state["task"].cancel()
                try:
                    async with asyncio.timeout(1.0):
                        await socket.close(code=1011)
                except Exception:
                    pass
                continue
            state["control"].append((payload, monotonic()))
            state["wake"].set()


call_manager = CallConnectionManager()
