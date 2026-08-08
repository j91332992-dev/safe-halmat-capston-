from fastapi.testclient import TestClient

from app.main import app
from app.models.entities import WorkerState
from app.routers.camera import _merge_detection


def test_real_camera_analysis_updates_worker_state():
    worker = WorkerState(
        worker_id="worker-camera-test",
        worker_name="테스트 작업자",
        helmet_id="helmet-camera-test",
        ppe_json="{}",
        hazard_json="{}",
    )
    _merge_detection(
        worker,
        {"mode": "real", "ppe": {"helmet": False, "vest": True}, "hazards": {"fire": False, "smoke": False}},
    )
    assert '"helmet": false' in worker.ppe_json
    assert '"fire": false' in worker.hazard_json


def test_operator_text_command_works_without_mock_endpoint(monkeypatch):
    async def no_tts(_message):
        return None
    monkeypatch.setattr("app.routers.audio.generate_tts", no_tts)
    with TestClient(app) as client:
        response = client.post(
            "/api/audio/command",
            json={"worker_id": "worker-001", "device_id": "helmet-001-av", "text": "현재 위험도 알려줘"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "risk_query"
        assert data["response"]
        assert "audio_url" in data


def test_camera_mock_endpoint_is_removed():
    with TestClient(app) as client:
        assert client.post("/api/camera/mock-detection", json={}).status_code == 404
