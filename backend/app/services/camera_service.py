from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from ..config import BASE_DIR


CAPTURE_DIR = BASE_DIR / "captures"
CAPTURE_DIR.mkdir(exist_ok=True)
LIVE_CAPTURE_DIR = CAPTURE_DIR / "_live"
LIVE_CAPTURE_DIR.mkdir(exist_ok=True)


async def save_frame(file: UploadFile, device_id: str) -> Path:
    suffix = Path(file.filename or "frame.jpg").suffix or ".jpg"
    # Keep transient high-rate frames out of the long-lived evidence folder.
    # Directory operations stay fast because this spool normally contains only
    # the processing frame and the single newest queued frame.
    target = LIVE_CAPTURE_DIR / f"{device_id}_{uuid4().hex}{suffix}"
    target.write_bytes(await file.read())
    return target

