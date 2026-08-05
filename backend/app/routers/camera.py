import asyncio
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db, utcnow
from ..models.entities import Device, Event, WorkerState
from ..schemas.api import MockDetectionIn
from ..services.camera_service import CAPTURE_DIR, save_frame
from ..services.event_service import create_event, event_to_dict
from ..services.risk_service import recalculate_risk
from ..services.serializers import worker_to_dict
from ..services.yolo_service import analyze_frame
from ..websocket import manager

router = APIRouter(prefix="/api/camera", tags=["camera"])


def _merge_detection(worker: WorkerState, analysis: dict) -> None:
    if analysis.get("mode") != "real":
        return
    current_ppe = json.loads(worker.ppe_json or "{}")
    current_hazards = json.loads(worker.hazard_json or "{}")
    current_ppe.update(analysis.get("ppe") or {})
    current_hazards.update(analysis.get("hazards") or {})
    worker.ppe_json = json.dumps(current_ppe, ensure_ascii=False)
    worker.hazard_json = json.dumps(current_hazards, ensure_ascii=False)


@router.post("/frame")
async def upload_frame(
    file: UploadFile = File(...),
    device_id: str = Form(...),
    worker_id: str = Form(...),
    helmet_id: str = Form("helmet-001"),
    db: Session = Depends(get_db),
):
    device = db.get(Device, device_id)
    worker = db.get(WorkerState, worker_id)
    if not device:
        raise HTTPException(404, "먼저 장치를 등록하세요.")
    if not worker:
        raise HTTPException(404, "작업자를 찾을 수 없습니다.")
    path = await save_frame(file, device_id)
    device.last_camera_at = utcnow()
    analysis = await asyncio.to_thread(analyze_frame, path.name)
    _merge_detection(worker, analysis)
    recalculate_risk(db, worker)

    hazards = analysis.get("hazards") or {}
    ppe = analysis.get("ppe") or {}
    missing = [name for name, worn in ppe.items() if worn is False]
    severity = "danger" if hazards.get("fire") or hazards.get("smoke") else "warning" if missing else "info"
    image_name = analysis.get("annotated_source") or path.name
    event = create_event(
        db,
        "CAMERA_FRAME",
        "카메라 프레임 분석 결과를 수신했습니다.",
        severity,
        worker_id=worker_id,
        device_id=device_id,
        details={
            "filename": image_name,
            "raw_filename": path.name,
            "url": f"/captures/{image_name}",
            "analysis": analysis,
            "helmet_id": helmet_id,
        },
    )
    db.commit()
    result = event_to_dict(event)
    result["worker"] = worker_to_dict(worker)
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


@router.get("/{device_id}/latest/image")
def latest_frame_image(device_id: str, db: Session = Depends(get_db)):
    event = (
        db.query(Event)
        .filter(Event.device_id == device_id, Event.event_type == "CAMERA_FRAME")
        .order_by(Event.created_at.desc())
        .first()
    )
    if not event:
        raise HTTPException(404, "수신된 카메라 프레임이 없습니다.")
    filename = json.loads(event.details_json).get("filename")
    filepath = CAPTURE_DIR / str(filename or "")
    if not filepath.exists():
        raise HTTPException(404, "이미지 파일을 찾을 수 없습니다.")
    return FileResponse(
        filepath,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"},
    )


@router.post("/mock-detection")
async def mock_detection(payload: MockDetectionIn, db: Session = Depends(get_db)):
    worker = db.get(WorkerState, payload.worker_id)
    if not worker:
        raise HTTPException(404, "작업자를 찾을 수 없습니다.")
    worker.ppe_json = json.dumps({"vest": payload.vest, "glove": payload.glove, "helmet": payload.helmet})
    worker.hazard_json = json.dumps({"fire": payload.fire, "smoke": payload.smoke})
    device = db.get(Device, payload.device_id)
    if device:
        device.last_camera_at = utcnow()

    details = payload.model_dump()
    latest_event = (
        db.query(Event)
        .filter(Event.device_id == payload.device_id, Event.event_type == "CAMERA_FRAME")
        .order_by(Event.created_at.desc())
        .first()
    )
    if latest_event and latest_event.details_json:
        latest = json.loads(latest_event.details_json)
        details.update({key: latest[key] for key in ("url", "filename") if key in latest})
    event = create_event(
        db,
        "MOCK_DETECTION",
        "카메라 탐지 테스트 결과가 반영되었습니다.",
        "danger" if payload.fire or payload.smoke else "warning" if not (payload.vest and payload.glove and payload.helmet) else "info",
        payload.worker_id,
        payload.device_id,
        details,
    )
    recalculate_risk(db, worker)
    db.commit()
    result = {"worker": worker_to_dict(worker), "event": event_to_dict(event)}
    await manager.broadcast("detection", result)
    return result