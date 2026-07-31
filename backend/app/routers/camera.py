import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db, utcnow
from ..models.entities import Device, Event, WorkerState
from ..schemas.api import MockDetectionIn
from ..services.camera_service import save_frame
from ..services.event_service import create_event, event_to_dict
from ..services.risk_service import recalculate_risk
from ..services.serializers import worker_to_dict
from ..services.yolo_service import analyze_frame_dummy
from ..websocket import manager

router = APIRouter(prefix="/api/camera", tags=["camera"])


@router.post("/frame")
async def upload_frame(
    file: UploadFile = File(...),
    device_id: str = Form(...),
    worker_id: str = Form(...),
    helmet_id: str = Form("helmet-001"),
    db: Session = Depends(get_db),
):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "먼저 장치를 등록하세요.")
    path = await save_frame(file, device_id)
    device.last_camera_at = utcnow()
    analysis = analyze_frame_dummy(path.name)
    event = create_event(
        db,
        "CAMERA_FRAME",
        "카메라 프레임을 수신했습니다.",
        worker_id=worker_id,
        device_id=device_id,
        details={"filename": path.name, "url": f"/captures/{path.name}", "analysis": analysis, "helmet_id": helmet_id},
    )
    db.commit()
    result = event_to_dict(event)
    await manager.broadcast("camera_frame", result)
    return result


@router.get("/{device_id}/latest")
def latest_frame(device_id: str, db: Session = Depends(get_db)):
    event = (
        db.query(Event)
        .filter(Event.device_id == device_id, Event.event_type == "CAMERA_FRAME")
        .order_by(Event.created_at.desc())
        .first()
    )
    if not event:
        return {"device_id": device_id, "received": False}
    return {"device_id": device_id, "received": True, **json.loads(event.details_json)}


@router.post("/mock-detection")
async def mock_detection(payload: MockDetectionIn, db: Session = Depends(get_db)):
    worker = db.get(WorkerState, payload.worker_id)
    if not worker:
        raise HTTPException(404, "작업자를 찾을 수 없습니다.")
    worker.ppe_json = json.dumps({"vest": payload.vest, "glove": payload.glove})
    worker.hazard_json = json.dumps({"fire": payload.fire, "smoke": payload.smoke})
    event = create_event(
        db,
        "MOCK_DETECTION",
        "더미 영상 탐지 결과가 반영되었습니다.",
        "danger" if payload.fire or payload.smoke else "info",
        payload.worker_id,
        payload.device_id,
        payload.model_dump(),
    )
    recalculate_risk(db, worker)
    db.commit()
    result = {"worker": worker_to_dict(worker), "event": event_to_dict(event)}
    await manager.broadcast("detection", result)
    return result

