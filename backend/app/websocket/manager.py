from collections import defaultdict
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.dashboard: list[WebSocket] = []
        self.devices: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect_dashboard(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.dashboard.append(websocket)

    async def connect_device(self, device_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.devices[device_id].append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.dashboard:
            self.dashboard.remove(websocket)
        for sockets in self.devices.values():
            if websocket in sockets:
                sockets.remove(websocket)

    async def broadcast(self, event_type: str, data: dict) -> None:
        payload = {"type": event_type, "data": data}
        dead: list[WebSocket] = []
        for socket in self.dashboard:
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

