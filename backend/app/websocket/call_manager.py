from collections import defaultdict
from hmac import compare_digest
from secrets import token_urlsafe
from time import monotonic

from fastapi import WebSocket

from ..config import settings


class CallConnectionManager:
    """In-memory relay for 16 kHz mono PCM. Audio is never written to disk."""

    def __init__(self) -> None:
        self.devices: dict[str, list[WebSocket]] = defaultdict(list)
        self.operators: dict[str, list[WebSocket]] = defaultdict(list)
        self.tickets: dict[str, tuple[str, float]] = {}

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

    async def relay_device_bytes(self, device_id: str, payload: bytes) -> None:
        await self._send_bytes(self.operators.get(device_id, []), payload)

    async def relay_operator_bytes(self, device_id: str, payload: bytes) -> None:
        await self._send_bytes(self.devices.get(device_id, []), payload)

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