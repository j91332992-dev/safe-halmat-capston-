import json

from sqlalchemy.orm import Session

from ..database import utcnow
from ..models.entities import Device
from ..schemas.api import DeviceRegister, Heartbeat


def register_device(db: Session, data: DeviceRegister) -> Device:
    device = db.get(Device, data.device_id)
    if not device:
        device = Device(device_id=data.device_id, device_type=data.device_type)
        db.add(device)
    for field in ("organization_id", "site_id", "worker_id", "helmet_id", "device_type", "firmware_version", "ip", "mac"):
        setattr(device, field, getattr(data, field))
    mark_device_seen(device)
    db.flush()
    return device


def mark_device_seen(device: Device, channel: str | None = None) -> None:
    now = utcnow()
    device.online = True
    device.last_seen = now
    if channel == "camera":
        device.last_camera_at = now
    elif channel == "audio":
        device.last_audio_at = now
    elif channel == "button":
        device.last_button_at = now
    elif channel == "uwb":
        device.last_uwb_at = now


def update_heartbeat(db: Session, data: Heartbeat) -> Device:
    device = db.get(Device, data.device_id)
    if not device:
        device = Device(
            device_id=data.device_id,
            device_type="position_device" if "uwb" in data.device_id else "assistant_device",
            organization_id=data.organization_id,
            site_id=data.site_id,
            worker_id=data.worker_id,
            helmet_id=data.helmet_id,
        )
        db.add(device)
    device.rssi = data.rssi
    device.battery = data.battery
    device.component_status_json = json.dumps(data.component_status, ensure_ascii=False)
    device.last_error = data.error
    mark_device_seen(device)
    db.flush()
    return device

