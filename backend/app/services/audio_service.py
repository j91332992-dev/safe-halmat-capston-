from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from ..config import BASE_DIR
from .whisper_service import transcribe_audio

AUDIO_DIR = BASE_DIR / "audio_data"
AUDIO_DIR.mkdir(exist_ok=True)


async def save_audio(file: UploadFile, device_id: str) -> Path:
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    target = AUDIO_DIR / f"{device_id}_{uuid4().hex}{suffix}"
    target.write_bytes(await file.read())
    return target


async def stt(audio_path: Path) -> str:
    # 실제 STT가 실패하거나 비활성화된 경우 명령을 만들지 않는다.
    # 상시 마이크에서 가짜 테스트 문장은 반복 오작동을 일으킬 수 있다.
    return (await transcribe_audio(audio_path) or "").strip()
