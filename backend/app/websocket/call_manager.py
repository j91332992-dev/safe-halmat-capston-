import asyncio
import json
from collections import defaultdict
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
        self.operators[device_id].append(websocket)
        if self.devices.get(device_id):
            await self.cancel_call_request(device_id, reason="answered")
            await self._send_text(self.devices[device_id], '{"type":"call_start"}')
            await websocket.send_json({"type": "call_status", "status": "connected"})
        else:
            await websocket.send_json({"type": "call_status", "status": "device_offline"})
        return True

    async def disconnect_device(self, device_id: str, websocket: WebSocket) -> None:
        self._remove(self.devices, device_id, websocket)
        if not self.devices.get(device_id):
            await self._send_text(self.operators.get(device_id, []), '{"type":"call_status","status":"device_offline"}')

    async def disconnect_operator(self, device_id: str, websocket: WebSocket) -> None:
        self._remove(self.operators, device_id, websocket)
        if not self.operators.get(device_id):
            await self._send_text(self.devices.get(device_id, []), '{"type":"call_stop"}')
            await self._resolve_active_request(device_id)

    async def relay_device_bytes(self, device_id: str, payload: bytes) -> None:
        await self._send_bytes(self.operators.get(device_id, []), payload)

    async def relay_operator_bytes(self, device_id: str, payload: bytes) -> None:
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

    @staticmethod
    async def _send_bytes(sockets: list[WebSocket], payload: bytes) -> None:
        for socket in list(sockets):
            try:
                await socket.send_bytes(payload)
            except Exception:
                if socket in sockets:
                    sockets.remove(socket)

    @staticmethod
    async def _send_text(sockets: list[WebSocket], payload: str) -> None:
        for socket in list(sockets):
            try:
                await socket.send_text(payload)
            except Exception:
                if socket in sockets:
                    sockets.remove(socket)


call_manager = CallConnectionManager()
