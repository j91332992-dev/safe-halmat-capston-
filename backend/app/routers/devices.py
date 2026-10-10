import json
import math
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db, utcnow
from ..models.entities import Anchor, Device, WorkerState
from ..schemas.api import ComponentResultIn, DeviceCommandIn, DeviceRegister, Heartbeat, HeadingCalibrationIn
from ..services.command_service import queue_command
from ..services.device_service import mark_device_seen, register_device, update_heartbeat
from ..services.serializers import device_to_dict
from ..services.orientation_service import live_status
from ..websocket import manager
from .auth import require_site

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.post("/{device_id}/heading-calibration")
async def calibrate_heading(device_id: str, payload: HeadingCalibrationIn, site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if not device or device.site_id != site_id:
        raise HTTPException(404, "장치를 찾을 수 없습니다.")
    status = live_status(device_id, json.loads(device.component_status_json or "{}"))
    yaw = status.get("imu_yaw_deg")
    received = status.get("imu_received_at")
    if (status.get("imu") != "ready" or not isinstance(yaw, (float, int))
            or not math.isfinite(yaw) or not received
            or (utcnow() - datetime.fromisoformat(received.rstrip("Z"))).total_seconds() > 15):
        raise HTTPException(409, "최신 방향 센서 데이터가 없습니다.")
    a, b = (db.get(Anchor, key) for key in payload.anchor_ids)
    worker = db.get(WorkerState, device.worker_id)
    if not a or not b or not worker or a.site_id != site_id or b.site_id != site_id or worker.site_id != site_id:
        raise HTTPException(409, "앵커 또는 작업자 위치가 없습니다.")
    # Face perpendicular to the wall, toward it from the worker's side.
    nx, ny = -(b.y - a.y), b.x - a.x
    if math.hypot(nx, ny) < .01:
        raise HTTPException(409, "두 앵커 위치가 같아 벽 방향을 구할 수 없습니다.")
    if nx * ((a.x + b.x) / 2 - worker.x) + ny * ((a.y + b.y) / 2 - worker.y) < 0:
        nx, ny = -nx, -ny
    reference = math.degrees(math.atan2(ny, nx)) % 360
    status["heading_calibration"] = {
        "offset_deg": reference - yaw, "reference_deg": reference,
        "anchor_ids": list(payload.anchor_ids), "yaw_deg": yaw,
        "calibrated_at": utcnow().isoformat() + "Z",
    }
    device.component_status_json = json.dumps(status, ensure_ascii=False)
    db.commit()
    result = device_to_dict(device)
    await manager.broadcast("heading_calibrated", result)
    return result


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


@router.post("/{device_id}/component-result")
async def component_result(device_id: str, payload: ComponentResultIn, db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "장치를 찾을 수 없습니다.")
    if payload.component == "speaker":
        device.last_speaker_at = utcnow()
        device.last_speaker_status = f"{payload.status}: {payload.command_id or '-'}"
    mark_device_seen(device)
    device.last_error = payload.detail if payload.status == "error" else None
    db.commit()
    result = device_to_dict(device)
    await manager.broadcast("component_result", result)
    return {"ok": payload.status == "ok", "device": result}


@router.post("/{device_id}/command")
async def command(device_id: str, payload: DeviceCommandIn, site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if not device or device.site_id != site_id:
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
    if record.command_type in {"play_tone", "play_ack", "play_audio", "play_alert"}:
        device.last_speaker_status = f"{record.command_type}: {record.status}"
    db.commit()
    result = {"command_id": record.command_id, "status": record.status, "delivered_connections": delivered}
    await manager.broadcast("device_command", {"device_id": device_id, "site_id": site_id, **result, "command_type": record.command_type})
    return result
