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
    if route.get("navigation_enabled"):
        # Recheck current incident and sensor ages after potentially slow synthesis.
        from ..database import SessionLocal
        from .evacuation_service import current_incident
        from .evacuation_navigation import latest_route, age
        with SessionLocal() as db:
            from ..models.entities import WorkerState
            worker = db.get(WorkerState, worker_id)
            current = current_incident(db, worker.site_id) if worker else None
            import json
            enabled = bool(current and current.incident_id == incident_id and
                           json.loads(current.details_json or "{}").get("navigation_enabled"))
        live = latest_route(worker_id)
        directional = route.get("action") not in {"map_unverified", "no_route", "location_stale", "heading_stale"}
        if directional:
            from .orientation_service import live_status
            with SessionLocal() as db:
                device = db.get(Device, device_id)
                status = live_status(device_id, json.loads(device.component_status_json or "{}")) if device else {}
            if status.get("imu") != "ready" or age(status.get("imu_received_at")) > 1:
                return {"sent": False, "reason": "heading_expired_during_synthesis"}
        if directional and (not worker or age(worker.last_valid_location_at) > 1.5):
            return {"sent": False, "reason": "location_expired_during_synthesis"}
        if not enabled or not live or live.get("action") != route.get("action"):
            return {"sent": False, "reason": "superseded_navigation"}
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


