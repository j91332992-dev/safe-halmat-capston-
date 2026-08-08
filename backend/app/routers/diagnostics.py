from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models.entities import Device
from ..services.presence_service import refresh_presence
from ..services.serializers import device_to_dict
from ..websocket import manager

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    devices, anchors = refresh_presence(db)
    return {
        "mode": settings.operation_mode,
        "server": "online",
        "devices_online": sum(1 for item in devices if item.online),
        "devices_total": len(devices),
        "anchors_online": sum(1 for item in anchors if item.online),
        "anchors_total": len(anchors),
        "recent_errors": [item.last_error for item in devices if item.last_error],
    }


@router.get("/devices")
def diagnostic_devices(db: Session = Depends(get_db)):
    devices, _ = refresh_presence(db)
    return [device_to_dict(row) for row in devices]


@router.get("/{device_id}")
def diagnostic_device(device_id: str, db: Session = Depends(get_db)):
    refresh_presence(db)
    row = db.get(Device, device_id)
    if not row:
        raise HTTPException(404, "장치를 찾을 수 없습니다.")
    return device_to_dict(row)


@router.post("/{device_id}/speaker-test")
async def speaker_test(device_id: str, db: Session = Depends(get_db)):
    row = db.get(Device, device_id)
    if not row:
        raise HTTPException(404, "장치를 찾을 수 없습니다.")

    payload = {"frequency": 1400, "duration": 1000}
    delivered = await manager.send_device_command(
        device_id,
        {
            "command_id": "diagnostic-speaker-test",
            "command_type": "play_tone",
            "payload": payload,
        },
    )
    row.last_speaker_status = f"play_tone: {'delivered' if delivered else 'not_connected'}"
    db.commit()
    return {
        "ok": bool(delivered),
        "device_id": device_id,
        "command_type": "play_tone",
        "payload": payload,
        "delivered_connections": delivered,
    }
