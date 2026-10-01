from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db, utcnow
from ..models.entities import Device, WorkerState
from ..schemas.api import ButtonEventIn
from ..services.event_service import create_event, event_to_dict
from ..services.device_service import mark_device_seen
from ..services.risk_service import recalculate_risk
from ..services.serializers import worker_to_dict
from ..websocket import manager

router = APIRouter(prefix="/api", tags=["button"])


@router.post("/button-event")
async def button_event(payload: ButtonEventIn, db: Session = Depends(get_db)):
    worker = db.get(WorkerState, payload.worker_id)
    if not worker:
        raise HTTPException(404, "작업자를 찾을 수 없습니다.")
    actions = {
        "single_press": "음성 녹음 요청",
        "double_press": "상태 보고 요청",
        "triple_press": "즉시 비상 신고",
        "long_press": "관리자 호출",
    }
    if payload.event_type == "triple_press":
        worker.emergency = True
    severity = "emergency" if payload.event_type == "triple_press" else "warning" if payload.event_type == "long_press" else "info"
    event = create_event(db, "BUTTON_EVENT", actions[payload.event_type], severity, payload.worker_id, payload.device_id, payload.model_dump(mode="json"))
    device = db.get(Device, payload.device_id)
    if device:
        mark_device_seen(device, "button")
    recalculate_risk(db, worker)
    db.commit()
    result = {"event": event_to_dict(event), "worker": worker_to_dict(worker)}
    await manager.broadcast("button_event", result)
    return result

