from __future__ import annotations

import time
import asyncio
import logging
import wave

from sqlalchemy.orm import Session

from ..models.entities import Device
from ..services.tts_generator_service import generate_tts
from ..websocket import manager

_last_guidance: dict[str, tuple[str, float]] = {}
MIN_REPEAT_SECONDS = 15.0
MIN_GUIDANCE_GAP_SECONDS = 3.0
_next_guidance: dict[str, float] = {}


def _guidance_throttled(worker_id, key, repeat_seconds, force=False):
    now = time.monotonic()
    if now < _next_guidance.get(worker_id, 0):
        return True
    previous_key, previous_at = _last_guidance.get(worker_id, ("", 0.0))
    return not force and previous_key == key and now - previous_at < repeat_seconds


def _audio_duration(path):
    if not path:
        return 0.0
    try:
        with wave.open(str(path), "rb") as audio:
            return audio.getnframes() / max(1, audio.getframerate())
    except (OSError, EOFError, wave.Error):
        return 0.0
_incident_locks: dict[str, asyncio.Lock] = {}


def _incident_lock(incident_id: str) -> asyncio.Lock:
    return _incident_locks.setdefault(incident_id, asyncio.Lock())


def _incident_active(incident_id: str) -> bool:
    from ..database import SessionLocal
    from ..models.entities import EvacuationIncident
    with SessionLocal() as db:
        incident = db.get(EvacuationIncident, incident_id)
        return bool(incident and incident.status in ("active", "pending_manager"))


def evacuation_voice_active(device_id: str) -> bool:
    """For rare notification arbitration, never called in PCM receive loops."""
    from ..database import SessionLocal
    from .evacuation_service import current_incident
    import json
    with SessionLocal() as db:
        device = db.get(Device, device_id)
        incident = current_incident(db, device.site_id) if device else None
        return bool(incident and json.loads(incident.details_json or "{}").get("navigation_enabled"))


async def stop_incident_guidance(incident_id: str, device_ids: list[str]) -> list[dict]:
    # The caller commits closure first. Serialize against the final audio send.
    results = []
    async with _incident_lock(incident_id):
        for device_id in device_ids:
            try:
                delivered = await asyncio.wait_for(manager.send_device_command(device_id, {
                    "command_type": "stop_evacuation", "payload": {"incident_id": incident_id},
                }), timeout=2.0)
                results.append({"device_id": device_id, "delivered": bool(delivered)})
            except Exception:
                logging.exception("Evacuation stop delivery failed: %s", device_id)
                results.append({"device_id": device_id, "delivered": False})
    logging.info("Evacuation stopped incident=%s deliveries=%s", incident_id, results)
    return results


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
    action = route.get("action") if route.get("navigation_enabled") else None
    key = f"{incident_id}:{action or message}"
    # State changes speak once; sustained turns can remind, straight walking stays quiet.
    repeat_seconds = (float("inf") if action in {"announce", "exit_near"}
                      else 6.0 if action in {"turn_left", "turn_right", "turn_back"}
                      else MIN_REPEAT_SECONDS)
    if _guidance_throttled(worker_id, key, repeat_seconds, force):
        return {"sent": False, "reason": "throttled"}

    if not _incident_active(incident_id):
        return {"sent": False, "reason": "incident_closed"}
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
    payload = {"message": message, "incident_id": incident_id, "audio_scope": "evacuation"}
    if audio_path:
        payload["audio_url"] = f"/tts/{audio_path.name}"
        payload["format"] = "wav"
        payload["sample_rate"] = 16000
    async with _incident_lock(incident_id):
        if not _incident_active(incident_id):
            return {"sent": False, "reason": "incident_closed_during_synthesis"}
        if _guidance_throttled(worker_id, key, repeat_seconds, force):
            return {"sent": False, "reason": "throttled"}
        delivered = await asyncio.wait_for(manager.send_device_command(
            device_id,
            {"command_type": command_type, "payload": payload},
        ), timeout=2.0)
        if delivered:
            sent_at = time.monotonic()
            _last_guidance[worker_id] = (key, sent_at)
            _next_guidance[worker_id] = sent_at + max(MIN_GUIDANCE_GAP_SECONDS, _audio_duration(audio_path) + 0.5)
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
        _next_guidance.pop(worker_id, None)
    else:
        _last_guidance.clear()
        _next_guidance.clear()


