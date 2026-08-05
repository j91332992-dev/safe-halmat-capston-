import logging
from pathlib import Path
from uuid import uuid4

from ..config import BASE_DIR, settings

logger = logging.getLogger(__name__)
TTS_OUTPUT_DIR = BASE_DIR / "tts_output"
TTS_OUTPUT_DIR.mkdir(exist_ok=True)


async def generate_tts(text: str) -> Path | None:
    if not settings.use_edge_tts or not text.strip():
        return None
    try:
        import edge_tts

        output = TTS_OUTPUT_DIR / f"{uuid4().hex}.mp3"
        await edge_tts.Communicate(text=text, voice=settings.tts_voice).save(str(output))
        return output
    except Exception as exc:
        logger.warning("TTS 생성 실패, 텍스트 응답만 사용: %s", exc)
        return None