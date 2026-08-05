import logging
from pathlib import Path

from ..config import settings

logger = logging.getLogger(__name__)


async def transcribe_audio(audio_path: Path) -> str | None:
    if not settings.use_whisper_stt or not settings.openai_api_key:
        return None
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        with audio_path.open("rb") as audio_file:
            transcript = await client.audio.transcriptions.create(
                model=settings.stt_model,
                file=audio_file,
                language=settings.stt_language,
            )
        text = transcript if isinstance(transcript, str) else getattr(transcript, "text", "")
        return str(text).strip() or None
    except Exception as exc:
        logger.warning("OpenAI STT 실패, 테스트 문장으로 대체: %s", exc)
        return None