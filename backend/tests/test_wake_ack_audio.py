from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.routers import audio
from app.services.wake_word_service import wake_word_gate


def test_wake_only_sends_speech_with_local_asset(monkeypatch):
    sent = []
    async def fake_stt(*args, **kwargs):
        return "투투스"
    async def fake_tts(text):
        assert text == "네, 말씀하세요."
        return Path("wake-test.wav")
    async def fake_send(device_id, command):
        sent.append(command)
        return 1
    monkeypatch.setattr(audio, "stt", fake_stt)
    monkeypatch.setattr(audio, "generate_tts", fake_tts)
    monkeypatch.setattr(audio.manager, "send_device_command", fake_send)
    wake_word_gate.reset()
    with TestClient(app) as client:
        result = client.post("/api/audio/upload", data={"device_id": "helmet-001-av", "worker_id": "worker-001"}, files={"file": ("wake.wav", b"test", "audio/wav")})
    assert result.status_code == 200
    assert result.json()["status"] == "armed"
    assert sent[-1]["command_type"] == "play_audio"
    assert sent[-1]["payload"]["local_asset"] == "acknowledgement"
    assert sent[-1]["payload"]["audio_url"] == "/tts/wake-test.wav"
    wake_word_gate.reset()
