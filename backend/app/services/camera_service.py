from pathlib import Path
from threading import Lock
from time import monotonic
from uuid import uuid4

from fastapi import UploadFile

from ..config import BASE_DIR


CAPTURE_DIR = BASE_DIR / "captures"
CAPTURE_DIR.mkdir(exist_ok=True)
LIVE_CAPTURE_DIR = CAPTURE_DIR / "_live"
LIVE_CAPTURE_DIR.mkdir(exist_ok=True)
_raw_lock = Lock()
_latest_raw: dict[str, tuple[bytes, dict]] = {}


def remember_raw_frame(device_id: str, jpeg: bytes, frame_id: int | None = None) -> None:
    """Keep a live preview independent of the slower YOLO result."""
    with _raw_lock:
        _latest_raw[device_id] = (jpeg, {"frame_id": frame_id, "received_monotonic": monotonic()})


def latest_raw_frame(device_id: str) -> tuple[bytes, dict] | None:
    with _raw_lock:
        return _latest_raw.get(device_id)


def save_frame_bytes(jpeg: bytes, device_id: str) -> Path:
    target = LIVE_CAPTURE_DIR / f"{device_id}_{uuid4().hex}.jpg"
    target.write_bytes(jpeg)
    return target


async def save_frame(file: UploadFile, device_id: str) -> Path:
    suffix = Path(file.filename or "frame.jpg").suffix or ".jpg"
    # Keep transient high-rate frames out of the long-lived evidence folder.
    # Directory operations stay fast because this spool normally contains only
    # the processing frame and the single newest queued frame.
    target = LIVE_CAPTURE_DIR / f"{device_id}_{uuid4().hex}{suffix}"
    target.write_bytes(await file.read())
    return target
