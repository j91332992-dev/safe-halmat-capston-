"""Exercise P4 wire framing and raw preview without starting YOLO inference."""

import struct

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import settings
from app.main import app
from app.routers import camera
from app.services import camera_service


URL = "/api/camera/stream/helmet-001-av?worker_id=worker-001"
TOKEN = "p4-camera-test-token"
# Only SOI/EOI validation is currently part of this endpoint's contract.
JPEG = b"\xff\xd8framing-fixture\xff\xd9"


@pytest.fixture
def camera_client(monkeypatch, tmp_path):
    jobs = []
    monkeypatch.setattr(settings, "camera_ingest_token", TOKEN)
    monkeypatch.setattr(camera, "CAPTURE_DIR", tmp_path)
    monkeypatch.setattr(camera_service, "LIVE_CAPTURE_DIR", tmp_path)
    monkeypatch.setattr(camera_service, "_latest_raw", {})
    monkeypatch.setattr(camera, "enqueue_camera_job", lambda job: jobs.append(job) or False)
    with TestClient(app) as client:
        yield client, jobs


def packet(frame_id=1, magic=b"HMR2"):
    return struct.pack(">4sQHH", magic, frame_id, 640, 480) + JPEG


def test_camera_stream_requires_token(camera_client):
    client, jobs = camera_client
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(URL):
            pass
    assert exc.value.code == 1008
    assert not jobs


def test_camera_stream_acks_and_publishes_raw_before_inference(camera_client):
    client, jobs = camera_client
    with client.websocket_connect(URL, headers={"X-Hanmir-Camera-Token": TOKEN}) as socket:
        socket.send_bytes(packet(7))
        ack = socket.receive_json()
        assert ack["frame_id"] == 7
        assert ack["type"] == "frame_ack"
        status = client.get("/api/camera/helmet-001-av/live").json()
        assert status["received"] is True
        assert status["frame_id"] == 7
        assert status["age_ms"] >= 0
        assert client.get("/api/camera/helmet-001-av/live/image").content == JPEG
    assert len(jobs) == 1
    assert jobs[0].frame_id == 7


@pytest.mark.parametrize("bad_packet", [packet(1), packet(2, b"BAD!")])
def test_camera_stream_rejects_duplicate_or_invalid_header(camera_client, bad_packet):
    client, jobs = camera_client
    with client.websocket_connect(URL, headers={"X-Hanmir-Camera-Token": TOKEN}) as socket:
        socket.send_bytes(packet(1))
        socket.receive_json()
        socket.send_bytes(bad_packet)
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
        assert exc.value.code == 1003
    assert len(jobs) == 1


def test_s3_multipart_still_accepts_frame_without_id(camera_client):
    client, jobs = camera_client
    response = client.post(
        "/api/camera/frame",
        data={"device_id": "helmet-001-av", "worker_id": "worker-001"},
        files={"file": ("frame.jpg", JPEG, "image/jpeg")},
    )
    assert response.status_code == 202
    assert response.json()["frame_id"] is None
    assert len(jobs) == 1
    assert client.get("/api/camera/helmet-001-av/live/image").content == JPEG
