import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from app.routers import uwb


def test_stream_uses_existing_handler_and_ordered_ack(monkeypatch):
    seen = []
    async def process(payload, compact_ack=False):
        seen.append(payload.cycle_id)
        return {"ok": True}
    monkeypatch.setattr(uwb, "upload_distances", process)
    app = FastAPI(); app.include_router(uwb.router)
    payload = dict(worker_id="w", helmet_id="h", device_id="d", uwb_tag_id="t", measurements=[], transport="wifi-ws")
    with TestClient(app).websocket_connect("/api/uwb/stream") as ws:
        for cycle in (1, 2):
            ws.send_json(dict(payload, cycle_id=cycle))
            assert ws.receive_text() == f"ack:{cycle}:200"
    assert seen == [1, 2]


def test_stream_rejects_invalid_payload():
    app = FastAPI(); app.include_router(uwb.router)
    with TestClient(app).websocket_connect("/api/uwb/stream") as ws:
        ws.send_text("not json")
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()
        assert exc.value.code == 1008
