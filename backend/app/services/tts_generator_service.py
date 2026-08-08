import hashlib
import logging
import wave
from pathlib import Path

from ..config import BASE_DIR, settings

logger = logging.getLogger(__name__)
TTS_OUTPUT_DIR = BASE_DIR / "tts_output"
TTS_OUTPUT_DIR.mkdir(exist_ok=True)


async def generate_tts(text: str) -> Path | None:
    """Generate a MAX98357A-friendly 16 kHz, 16-bit, mono PCM WAV file."""
    if not settings.use_edge_tts or not text.strip():
        return None
    cache_key = hashlib.sha256((settings.tts_voice + "\0" + text.strip()).encode("utf-8")).hexdigest()[:24]
    output = TTS_OUTPUT_DIR / f"{cache_key}.wav"
    if output.exists() and output.stat().st_size > 44:
        return output
    mp3_path = TTS_OUTPUT_DIR / f"{cache_key}.tmp.mp3"
    try:
        import edge_tts
        import miniaudio

        await edge_tts.Communicate(text=text, voice=settings.tts_voice).save(str(mp3_path))
        decoded = miniaudio.decode(
            mp3_path.read_bytes(),
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=1,
            sample_rate=16000,
        )
        with wave.open(str(output), "wb") as wav_file:
            wav_file.setnchannels(decoded.nchannels)
            wav_file.setsampwidth(decoded.sample_width)
            wav_file.setframerate(decoded.sample_rate)
            wav_file.writeframes(decoded.samples.tobytes())
        return output
    except Exception as exc:
        logger.warning("TTS WAV 생성 실패, 경고음으로 대체: %s", exc)
        output.unlink(missing_ok=True)
        return None
    finally:
        mp3_path.unlink(missing_ok=True)
