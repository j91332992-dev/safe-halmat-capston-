from fastapi.testclient import TestClient

from app.main import app


def test_camera_detection_updates_helmet_and_risk():
    with TestClient(app) as client:
        response = client.post(
            "/api/camera/mock-detection",
            json={
                "worker_id": "worker-001",
                "device_id": "helmet-001-av",
                "helmet": False,
                "vest": True,
                "glove": True,
                "fire": False,
                "smoke": False,
            },
        )
        assert response.status_code == 200
        worker = response.json()["worker"]
        assert worker["ppe"]["helmet"] is False
        assert any(item["reason"] == "안전모 미착용" for item in worker["risk_reasons"])


def test_voice_command_works_without_openai_key():
    with TestClient(app) as client:
        response = client.post(
            "/api/audio/mock-command",
            json={"worker_id": "worker-001", "device_id": "helmet-001-av", "text": "현재 위험도 알려줘"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "risk_query"
        assert data["response"]
        assert "audio_url" in data