from pathlib import Path
from threading import Lock
from time import monotonic
from uuid import uuid4

from fastapi import UploadFile

from ..config import BASE_DIR
from .camera_brightness import preview_jpeg


CAPTURE_DIR = BASE_DIR / "captures"
CAPTURE_DIR.mkdir(exist_ok=True)
LIVE_CAPTURE_DIR = CAPTURE_DIR / "_live"
LIVE_CAPTURE_DIR.mkdir(exist_ok=True)
_raw_lock = Lock()
_latest_raw: dict[str, tuple[bytes, dict]] = {}
_latest_preview: dict[str, tuple[bytes, dict]] = {}


def remember_raw_frame(device_id: str, jpeg: bytes, frame_id: int | None = None) -> None:
    """Keep a live preview independent of the slower YOLO result."""
    received = monotonic()
    preview = preview_jpeg(jpeg)
    with _raw_lock:
        metadata = {"frame_id": frame_id, "received_monotonic": received}
        _latest_raw[device_id] = (jpeg, metadata)
        _latest_preview[device_id] = (preview, metadata)

def latest_preview_frame(device_id: str):
    with _raw_lock:
        return _latest_preview.get(device_id)


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
