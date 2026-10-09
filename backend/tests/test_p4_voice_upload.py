"""The new P4 upload flag must not break the S3 wake or emergency paths."""

from fastapi.testclient import TestClient

from app.main import app
from app.routers import audio
from app.services.voice_execution_gate import voice_execution_gate
from app.services.wake_word_service import wake_word_gate


def test_p4_local_wake_sends_command_only_to_stt(monkeypatch):
    seen = []

    async def fake_stt(_path, *, command_only=False):
        seen.append(command_only)
        return "내 위치 알려줘"

    async def no_tts(_message):
        return None

    monkeypatch.setattr(audio, "stt", fake_stt)
    monkeypatch.setattr(audio, "generate_tts", no_tts)
    voice_execution_gate.reset()
    with TestClient(app) as client:
        response = client.post(
            "/api/audio/upload",
            data={"device_id": "helmet-001-av", "worker_id": "worker-001", "wake_detected": "true"},
            files={"file": ("command.wav", b"RIFFfake", "audio/wav")},
        )
    assert response.status_code == 200
    result = response.json()
    assert seen == [True]
    assert result["status"] == "command"
    assert result["wake_reason"] == "device_wake"
    assert result["intent"] == "location_query"
    assert "stt" in result["timings_ms"]


def test_s3_quiet_fire_report_bypasses_wake(monkeypatch):
    async def fake_stt(_path, *, command_only=False):
        assert command_only is False
        return "불이야"

    async def no_tts(_message):
        return None

    monkeypatch.setattr(audio, "stt", fake_stt)
    monkeypatch.setattr(audio, "generate_tts", no_tts)
    wake_word_gate.reset()
    voice_execution_gate.reset()
    with TestClient(app) as client:
        response = client.post(
            "/api/audio/upload",
            data={"device_id": "helmet-001-av", "worker_id": "worker-001", "sound_db": "45"},
            files={"file": ("fire.wav", b"RIFFfake", "audio/wav")},
        )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "command"
    assert result["wake_reason"] == "life_critical_bypass"
    assert result["intent"] == "fire_report"
