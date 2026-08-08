import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.entities import Device
from ..schemas.api import DeviceCommandIn, DeviceRegister, Heartbeat
from ..services.command_service import queue_command
from ..services.device_service import register_device, update_heartbeat
from ..services.serializers import device_to_dict
from ..websocket import manager

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.post("/register")
async def register(payload: DeviceRegister, db: Session = Depends(get_db)):
    device = register_device(db, payload)
    db.commit()
    result = device_to_dict(device)
    await manager.broadcast("device_registered", result)
    return result


@router.post("/heartbeat")
async def heartbeat(payload: Heartbeat, db: Session = Depends(get_db)):
    device = update_heartbeat(db, payload)
    db.commit()
    result = device_to_dict(device)
    await manager.broadcast("heartbeat", result)
    return {"ok": True, "server_mode": __import__("app.config", fromlist=["settings"]).settings.operation_mode, "device": result}


@router.post("/{device_id}/command")
async def command(device_id: str, payload: DeviceCommandIn, db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "장치를 찾을 수 없습니다.")
    record = queue_command(db, device_id, payload.command_type, payload.payload)
    delivered = await manager.send_device_command(
        device_id,
        {
            "command_id": record.command_id,
            "command_type": record.command_type,
            "payload": json.loads(record.payload_json),
        },
    )
    record.status = "delivered" if delivered else "queued"
    device.last_speaker_status = f"{record.command_type}: {record.status}"
    db.commit()
    result = {"command_id": record.command_id, "status": record.status, "delivered_connections": delivered}
    await manager.broadcast("device_command", {"device_id": device_id, **result, "command_type": record.command_type})
    return result

