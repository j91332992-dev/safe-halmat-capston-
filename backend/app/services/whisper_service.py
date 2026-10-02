import logging
from pathlib import Path

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


async def transcribe_audio(audio_path: Path, *, command_only: bool = False) -> str | None:
    if not settings.use_whisper_stt or not settings.openai_api_key:
        return None
    try:
        client = _get_client()
        with audio_path.open("rb") as audio_file:
            request = dict(
                model=settings.stt_model,
                file=audio_file,
                prompt=settings.stt_command_prompt if command_only else settings.stt_prompt,
            )
            if settings.stt_model == "gpt-transcribe":
                request["extra_body"] = {"languages": [settings.stt_language]}
            else:
                request["language"] = settings.stt_language
            transcript = await client.audio.transcriptions.create(**request)
        text = transcript if isinstance(transcript, str) else getattr(transcript, "text", "")
        return str(text).strip() or None
    except Exception as exc:
        logger.warning("OpenAI STT 실패, 전사 없이 종료: %s", exc)
        return None
