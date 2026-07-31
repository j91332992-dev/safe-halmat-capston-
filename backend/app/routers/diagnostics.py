from datetime import timedelta
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db, utcnow
from ..models.entities import Anchor, Device
from ..schemas.api import MockScenarioIn
from ..services.serializers import device_to_dict

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


def refresh_online_state(db: Session) -> list[Device]:
    devices = db.query(Device).all()
    cutoff = utcnow() - timedelta(seconds=settings.device_offline_seconds)
    for device in devices:
        device.online = device.last_seen >= cutoff or settings.operation_mode == "mock"
    db.flush()
    return devices


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    devices = refresh_online_state(db)
    anchors = db.query(Anchor).all()
    db.commit()
    return {
        "mode": settings.operation_mode,
        "server": "online",
        "devices_online": sum(1 for d in devices if d.online),
        "devices_total": len(devices),
        "anchors_online": sum(1 for a in anchors if a.online),
        "anchors_total": len(anchors),
        "recent_errors": [d.last_error for d in devices if d.last_error],
    }


@router.get("/devices")
def diagnostic_devices(db: Session = Depends(get_db)):
    rows = refresh_online_state(db)
    db.commit()
    return [device_to_dict(row) for row in rows]


@router.get("/{device_id}")
def diagnostic_device(device_id: str, db: Session = Depends(get_db)):
    row = db.get(Device, device_id)
    if not row:
        raise HTTPException(404, "장치를 찾을 수 없습니다.")
    return device_to_dict(row)


@router.post("/{device_id}/speaker-test")
def speaker_test(device_id: str, db: Session = Depends(get_db)):
    row = db.get(Device, device_id)
    if not row:
        raise HTTPException(404, "장치를 찾을 수 없습니다.")
    row.last_speaker_status = "play_tone: diagnostic requested"
    db.commit()
    return {"ok": True, "device_id": device_id, "command_type": "play_tone"}


@router.post("/mock/scenario")
def mock_scenario_alias(payload: MockScenarioIn):
    return {"ok": True, "forward_to": "/api/system/mock/scenario", "payload": payload.model_dump()}

