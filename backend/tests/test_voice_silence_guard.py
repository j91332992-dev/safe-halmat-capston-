import asyncio
import wave
from app.services import whisper_service


def test_zero_pcm_never_calls_stt(tmp_path, monkeypatch):
    path = tmp_path / "silent.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(bytes(32000))
    records = []
    monkeypatch.setattr(whisper_service, "record_voice", lambda *a, **kw: records.append(kw))
    def unexpected():
        raise AssertionError("Silent PCM must not reach paid STT")
    monkeypatch.setattr(whisper_service, "_get_client", unexpected)
    assert asyncio.run(whisper_service.transcribe_audio(path)) is None
    assert records[-1]["reason"] == "PCM_ALL_ZERO"
