from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from ..config import BASE_DIR


AUDIO_DIR = BASE_DIR / "audio_data"
AUDIO_DIR.mkdir(exist_ok=True)


async def save_audio(file: UploadFile, device_id: str) -> Path:
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    target = AUDIO_DIR / f"{device_id}_{uuid4().hex}{suffix}"
    target.write_bytes(await file.read())
    return target


def dummy_stt(_path: Path) -> str:
    return "현재 위험도 알려줘"

