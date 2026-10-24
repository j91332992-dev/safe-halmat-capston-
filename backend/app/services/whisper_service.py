import logging
from pathlib import Path
from time import perf_counter
import wave
import numpy as np
from .voice_trace import record_voice

from ..config import settings

logger = logging.getLogger(__name__)
_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import AsyncOpenAI

        # A voice interaction should fail promptly rather than waiting through
        # the SDK's automatic retries. Both values remain environment-configurable.
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.stt_timeout_seconds,
            max_retries=0,
        )
    return _client


async def transcribe_audio(audio_path: Path, *, command_only: bool = False, confirmation_mode: bool = False) -> str | None:
    started = perf_counter()
    metrics = {}
    try:
        with wave.open(str(audio_path), "rb") as wav:
            metrics = dict(sample_rate=wav.getframerate(), channels=wav.getnchannels(),
                           sample_width=wav.getsampwidth(), frames=wav.getnframes(),
                           duration_ms=round(wav.getnframes() / wav.getframerate() * 1000))
            if wav.getsampwidth() == 2:
                pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float64)
                if pcm.size:
                    metrics.update(peak=int(np.max(np.abs(pcm))), rms=round(float(np.sqrt(np.mean(pcm * pcm))), 2),
                                   clipped_fraction=round(float(np.mean(np.abs(pcm) >= 32767)), 6))
    except (OSError, ValueError, EOFError, wave.Error):
        metrics["wav_status"] = "unreadable"
    record_voice("audio_received", audio_path.name, model=settings.stt_model,confirmation_mode=confirmation_mode, **metrics)
    if metrics.get("peak") == 0:
        record_voice("stt", audio_path.name, status="skipped", reason="PCM_ALL_ZERO",
                     duration_ms=round((perf_counter()-started)*1000, 1))
        return None
    if not settings.use_whisper_stt or not settings.openai_api_key:
        record_voice("stt", audio_path.name, status="disabled" if not settings.use_whisper_stt else "missing_key")
        return None
    try:
        client = _get_client()
        with audio_path.open("rb") as audio_file:
            request = dict(
                model=settings.stt_model,
                file=audio_file,
                prompt=settings.stt_command_prompt if command_only else settings.stt_prompt,
            )
            if confirmation_mode:
                # Short yes/help responses: do not prime a sentence that can be echoed as speech.
                request.pop('prompt',None)
            if settings.stt_model == "gpt-transcribe":
                request["extra_body"] = {"languages": [settings.stt_language]}
            else:
                request["language"] = settings.stt_language
            transcript = await client.audio.transcriptions.create(**request)
        text = transcript if isinstance(transcript, str) else getattr(transcript, "text", "")
        record_voice("stt", audio_path.name, status="ok" if str(text).strip() else "empty",
                     transcript=str(text).strip()[:2000], model=settings.stt_model,
                     duration_ms=round((perf_counter()-started)*1000, 1))
        return str(text).strip() or None
    except Exception as exc:
        record_voice("stt", audio_path.name, status="service_error", error_type=type(exc).__name__,
                     http_status=getattr(exc, "status_code", None), duration_ms=round((perf_counter()-started)*1000, 1))
        logger.warning("OpenAI STT failed: %s", type(exc).__name__)
        return None
