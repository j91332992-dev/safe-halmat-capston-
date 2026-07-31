from datetime import datetime
import json
from typing import Any


def parse_json(value: str | None, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (json.JSONDecodeError, TypeError):
        return fallback


def iso(value: datetime | None) -> str | None:
    return value.isoformat() + "Z" if value else None


def device_to_dict(device) -> dict:
    return {
        "device_id": device.device_id,
        "device_type": device.device_type,
        "organization_id": device.organization_id,
        "site_id": device.site_id,
        "worker_id": device.worker_id,
        "helmet_id": device.helmet_id,
        "ip": device.ip,
        "mac": device.mac,
        "rssi": device.rssi,
        "battery": device.battery,
        "firmware_version": device.firmware_version,
        "online": device.online,
        "component_status": parse_json(device.component_status_json, {}),
        "last_error": device.last_error,
        "last_seen": iso(device.last_seen),
        "last_camera_at": iso(device.last_camera_at),
        "last_audio_at": iso(device.last_audio_at),
        "last_button_at": iso(device.last_button_at),
        "last_uwb_at": iso(device.last_uwb_at),
        "last_speaker_status": device.last_speaker_status,
    }


def worker_to_dict(worker) -> dict:
    return {
        "worker_id": worker.worker_id,
        "worker_name": worker.worker_name,
        "helmet_id": worker.helmet_id,
        "x": worker.x,
        "y": worker.y,
        "confidence": worker.confidence,
        "current_zone": worker.current_zone,
        "risk_score": worker.risk_score,
        "risk_level": worker.risk_level,
        "risk_reasons": parse_json(worker.reasons_json, []),
        "ppe": parse_json(worker.ppe_json, {}),
        "hazards": parse_json(worker.hazard_json, {}),
        "emergency": worker.emergency,
        "updated_at": iso(worker.updated_at),
    }

