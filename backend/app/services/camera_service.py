from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from ..config import BASE_DIR


CAPTURE_DIR = BASE_DIR / "captures"
CAPTURE_DIR.mkdir(exist_ok=True)


async def save_frame(file: UploadFile, device_id: str) -> Path:
    suffix = Path(file.filename or "frame.jpg").suffix or ".jpg"
    target = CAPTURE_DIR / f"{device_id}_{uuid4().hex}{suffix}"
    target.write_bytes(await file.read())
    return target

