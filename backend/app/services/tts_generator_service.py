import hashlib
import logging
import wave
import asyncio
from time import perf_counter
from uuid import uuid4
from pathlib import Path

from ..config import BASE_DIR, settings
from .voice_trace import record_voice

logger = logging.getLogger(__name__)
TTS_OUTPUT_DIR = BASE_DIR / "tts_output"
TTS_OUTPUT_DIR.mkdir(exist_ok=True)


async def generate_tts(text: str) -> Path | None:
    """Generate a MAX98357A-friendly 16 kHz, 16-bit, mono PCM WAV file."""
    started = perf_counter()
    if not settings.use_edge_tts or not text.strip():
        return None
    cache_key = hashlib.sha256((settings.tts_voice + "\0" + text.strip()).encode("utf-8")).hexdigest()[:24]
    output = TTS_OUTPUT_DIR / f"{cache_key}.wav"
    if output.exists() and output.stat().st_size > 44:
        record_voice("tts", cache_key, status="cached", bytes=output.stat().st_size,
                     duration_ms=round((perf_counter()-started)*1000, 1))
        return output
    nonce = uuid4().hex
    mp3_path = TTS_OUTPUT_DIR / f"{cache_key}.{nonce}.tmp.mp3"
    wav_path = TTS_OUTPUT_DIR / f"{cache_key}.{nonce}.tmp.wav"
    try:
        import edge_tts
        import miniaudio

        await asyncio.wait_for(edge_tts.Communicate(text=text, voice=settings.tts_voice).save(str(mp3_path)),
                               timeout=settings.tts_timeout_seconds)
        decoded = miniaudio.decode(
            mp3_path.read_bytes(),
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=1,
            sample_rate=16000,
        )
        with wave.open(str(wav_path), "wb") as wav_file:
            wav_file.setnchannels(decoded.nchannels)
            wav_file.setsampwidth(decoded.sample_width)
            wav_file.setframerate(decoded.sample_rate)
            wav_file.writeframes(decoded.samples.tobytes())
        wav_path.replace(output)
        record_voice("tts", cache_key, status="generated", provider="edge-tts",
                     bytes=output.stat().st_size, duration_ms=round((perf_counter()-started)*1000, 1))
        return output
    except Exception as exc:
        logger.warning("TTS WAV generation failed; tone fallback: type=%s status=%s",
                       type(exc).__name__, getattr(exc, "status", None))
        record_voice("tts", cache_key, status="failed", error_type=type(exc).__name__,
                     http_status=getattr(exc, "status", None), duration_ms=round((perf_counter()-started)*1000, 1))
        return None
    finally:
        mp3_path.unlink(missing_ok=True)
        wav_path.unlink(missing_ok=True)
