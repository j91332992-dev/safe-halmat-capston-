from __future__ import annotations

import time

from sqlalchemy.orm import Session

from ..models.entities import Device
from ..services.tts_generator_service import generate_tts
from ..websocket import manager

_last_guidance: dict[str, tuple[str, float]] = {}
MIN_REPEAT_SECONDS = 8.0


def assistant_device_id(db: Session, worker_id: str) -> str | None:
    device = (
        db.query(Device)
        .filter(Device.worker_id == worker_id, Device.device_type == "assistant_device")
        .first()
    )
    return device.device_id if device else None



async def send_helmet_guidance(
    worker_id: str,
    device_id: str | None,
    incident_id: str,
    route: dict,
    *,
    force: bool = False,
) -> dict:
    if not device_id:
        return {"sent": False, "reason": "device_unavailable"}
    if not manager.devices.get(device_id):
        return {"sent": False, "reason": "helmet_offline", "device_id": device_id}
    message = str(route.get("message") or next(iter(route.get("instructions") or []), "")).strip()
    if not message:
        return {"sent": False, "reason": "alert_message_unavailable"}
    key = f"{incident_id}:{message}"
    now = time.monotonic()
    previous_key, previous_at = _last_guidance.get(worker_id, ("", 0.0))
    if not force and previous_key == key and now - previous_at < MIN_REPEAT_SECONDS:
        return {"sent": False, "reason": "throttled"}

    audio_path = await generate_tts(message)
    command_type = "play_audio" if audio_path else "play_alert"
    payload = {"message": message}
    if audio_path:
        payload["audio_url"] = f"/tts/{audio_path.name}"
        payload["format"] = "wav"
        payload["sample_rate"] = 16000
    delivered = await manager.send_device_command(
        device_id,
        {"command_type": command_type, "payload": payload},
    )
    if delivered:
        _last_guidance[worker_id] = (key, now)
    return {
        "sent": bool(delivered),
        "device_id": device_id,
        "command_type": command_type,
        "audio_url": payload.get("audio_url"),
        "message": message,
    }


def clear_guidance(worker_id: str | None = None) -> None:
    if worker_id:
        _last_guidance.pop(worker_id, None)
    else:
        _last_guidance.clear()


