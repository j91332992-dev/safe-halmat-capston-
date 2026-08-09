import asyncio
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db, utcnow
from ..models.entities import Device, Event, WorkerState
from ..services.camera_service import CAPTURE_DIR, save_frame
from ..services.event_service import create_event, event_to_dict
from ..services.device_service import mark_device_seen
from ..services.evacuation_service import evacuation_snapshot, trigger_fire
from ..services.evacuation_guidance_service import assistant_device_id, send_helmet_guidance
from ..services.risk_service import recalculate_risk
from ..services.serializers import worker_to_dict
from ..services.yolo_service import analyze_frame
from ..websocket import manager

router = APIRouter(prefix="/api/camera", tags=["camera"])


def _upsert_camera_event(
    db: Session,
    *,
    worker_id: str,
    device_id: str,
    severity: str,
    details: dict,
) -> Event:
    """Keep one rolling camera event per device instead of flooding the event log."""
    rows = (
        db.query(Event)
        .filter(Event.device_id == device_id, Event.event_type == "CAMERA_FRAME")
        .order_by(Event.created_at.desc())
        .all()
    )
    event = rows[0] if rows else None
    for stale in rows[1:]:
        db.delete(stale)
    if event is None:
        return create_event(
            db,
            "CAMERA_FRAME",
            "카메라 프레임 분석 결과를 수신했습니다.",
            severity,
            worker_id=worker_id,
            device_id=device_id,
            details=details,
        )
    event.worker_id = worker_id
    event.severity = severity
    event.status = "open"
    event.message = "카메라 프레임 분석 결과를 수신했습니다."
    event.details_json = json.dumps(details, ensure_ascii=False)
    event.created_at = utcnow()
    return event


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
    mark_device_seen(device, "camera")
    analysis = await asyncio.to_thread(analyze_frame, path.name)
    _merge_detection(worker, analysis)
    recalculate_risk(db, worker)

    hazards = analysis.get("hazards") or {}
    evacuation_created = False
    if hazards.get("fire") or hazards.get("large_fire"):
        _, evacuation_created = trigger_fire(db, "yolo", worker_id, {"analysis": analysis, "filename": path.name})
    ppe = analysis.get("ppe") or {}
    missing = [name for name, worn in ppe.items() if worn is False]
    severity = "danger" if hazards.get("fire") or hazards.get("smoke") else "warning" if missing else "info"
    image_name = analysis.get("annotated_source") or path.name
    event = _upsert_camera_event(
        db,
        worker_id=worker_id,
        device_id=device_id,
        severity=severity,
        details={
            "filename": image_name,
            "raw_filename": path.name,
            "url": f"/captures/{image_name}",
            "analysis": analysis,
            "helmet_id": helmet_id,
            "evacuation_created": evacuation_created,
        },
    )
    db.commit()
    result = event_to_dict(event)
    result["worker"] = worker_to_dict(worker)
    result["evacuation"] = evacuation_snapshot(db)
    if evacuation_created and result["evacuation"]["incident"]:
        route = result["evacuation"]["routes"].get(worker_id)
        if route:
            result["helmet_guidance"] = await send_helmet_guidance(worker_id, assistant_device_id(db, worker_id), result["evacuation"]["incident"]["incident_id"], route, force=True)
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
