import asyncio
from collections import defaultdict, deque
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.dashboard: dict[str, list[WebSocket]] = defaultdict(list)
        self.workers: dict[tuple[str, str], list[WebSocket]] = defaultdict(list)
        self.devices: dict[str, list[WebSocket]] = defaultdict(list)
        self._outputs: dict[WebSocket, dict] = {}
        self.stats = {'sent': 0, 'coalesced': 0, 'slow_clients_closed': 0, 'send_errors': 0}

    async def connect_dashboard(self, site_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.dashboard[site_id].append(websocket)

    async def connect_worker(self, site_id: str, worker_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.workers[site_id, worker_id].append(websocket)

    async def connect_device(self, device_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.devices[device_id].append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        state = self._outputs.pop(websocket, None)
        if state and state['task'] is not asyncio.current_task():
            state['task'].cancel()
        for sockets in self.dashboard.values():
            if websocket in sockets:
                sockets.remove(websocket)
        for sockets in self.workers.values():
            if websocket in sockets:
                sockets.remove(websocket)
        for sockets in self.devices.values():
            if websocket in sockets:
                sockets.remove(websocket)

    @staticmethod
    def _site_id(data: dict) -> str | None:
        direct = data.get("site_id")
        if isinstance(direct, str):
            return direct
        for key in ("device", "worker", "event", "incident"):
            nested = data.get(key)
            if isinstance(nested, dict) and isinstance(nested.get("site_id"), str):
                return nested["site_id"]
        return None

    async def broadcast(self, event_type: str, data: dict, site_id: str | None = None) -> None:
        target_site = site_id or self._site_id(data)
        # Fail closed: an event without a site must never be sent to every company.
        if not target_site:
            return
        payload = {"type": event_type, "data": data}
        # Telemetry ingestion must never wait for a dashboard's network writes.
        # Keep only the newest replaceable telemetry for the same subject.
        subject = data.get('device_id') or data.get('worker_id') or (data.get('worker') or {}).get('worker_id')
        key = (event_type, subject) if event_type in {'orientation', 'location', 'heartbeat'} else None
        for socket in list(self.dashboard.get(target_site, [])):
            self._enqueue(socket, payload, key)
        if event_type in {"orientation", "location", "heartbeat"}:
            worker_id = data.get("worker_id") or (data.get("worker") or {}).get("worker_id")
            if isinstance(worker_id, str):
                for socket in list(self.workers.get((target_site, worker_id), [])):
                    self._enqueue(socket, payload, key)

    def _enqueue(self, socket, payload, key):
        state = self._outputs.get(socket)
        if state is None:
            state = {'queue': deque(), 'wake': asyncio.Event()}
            self._outputs[socket] = state
            state['task'] = asyncio.create_task(self._write(socket, state), name='dashboard-writer')
        if key is not None:
            for index, (old_key, _) in enumerate(state['queue']):
                if old_key == key:
                    del state['queue'][index]
                    self.stats['coalesced'] += 1
                    break
        if len(state['queue']) >= 128:
            # Do not silently discard administrator alarms. Close a stalled peer
            # so its reconnect performs the authoritative HTTP snapshot refresh.
            self.stats['slow_clients_closed'] += 1
            self.disconnect(socket)
            asyncio.create_task(self._close(socket))
            return
        state['queue'].append((key, payload))
        state['wake'].set()

    async def _write(self, socket, state):
        try:
            while True:
                await state['wake'].wait()
                while state['queue']:
                    _, payload = state['queue'].popleft()
                    async with asyncio.timeout(.5):
                        await socket.send_json(payload)
                    self.stats['sent'] += 1
                state['wake'].clear()
        except asyncio.CancelledError:
            raise
        except Exception:
            self.stats['send_errors'] += 1
            self.disconnect(socket)
            await self._close(socket)

    @staticmethod
    async def _close(socket):
        try:
            async with asyncio.timeout(.5):
                await socket.close(code=1013)
        except Exception:
            pass

    async def send_device_command(self, device_id: str, payload: dict) -> int:
        delivered = 0
        for socket in list(self.devices.get(device_id, [])):
            try:
                await socket.send_json(payload)
                delivered += 1
            except Exception:
                self.disconnect(socket)
        return delivered


manager = ConnectionManager()
