from collections import defaultdict
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.dashboard: dict[str, list[WebSocket]] = defaultdict(list)
        self.workers: dict[tuple[str, str], list[WebSocket]] = defaultdict(list)
        self.devices: dict[str, list[WebSocket]] = defaultdict(list)

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
        dead: list[WebSocket] = []
        for socket in list(self.dashboard.get(target_site, [])):
            try:
                await socket.send_json(payload)
            except Exception:
                dead.append(socket)
        if event_type in {"orientation", "location", "heartbeat"}:
            worker_id = data.get("worker_id") or (data.get("worker") or {}).get("worker_id")
            if isinstance(worker_id, str):
                for socket in list(self.workers.get((target_site, worker_id), [])):
                    try:
                        await socket.send_json(payload)
                    except Exception:
                        dead.append(socket)
        for socket in dead:
            self.disconnect(socket)

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
