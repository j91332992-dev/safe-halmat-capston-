import asyncio
from contextlib import suppress
from dataclasses import dataclass
import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db, utcnow
from ..models.entities import Device, Event, WorkerState
from ..services.camera_service import CAPTURE_DIR, save_frame
from ..services.event_service import create_event, event_to_dict
from ..services.device_service import mark_device_seen
from ..services.evacuation_service import evacuation_snapshot, trigger_fire
from ..services.evacuation_guidance_service import assistant_device_id, send_helmet_guidance
from ..services.risk_service import recalculate_risk
from ..services.serializers import worker_to_dict
from ..services.yolo_service import analyze_frame
from ..services.inference_priority import voice_requests_active, wait_for_voice_idle
from ..websocket import manager

router = APIRouter(prefix="/api/camera", tags=["camera"])
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CameraJob:
    filename: str
    device_id: str
    worker_id: str
    helmet_id: str


# Only retain the newest waiting frame. YOLO processes one frame at a time;
# allowing a backlog would make fire/PPE decisions describe old video.
_camera_queue: asyncio.Queue[CameraJob] | None = None
_camera_worker_task: asyncio.Task | None = None
_dropped_stale_frames = 0


def enqueue_camera_job(job: CameraJob) -> bool:
    """Queue the newest frame and return True when an older queued frame was dropped."""
    global _dropped_stale_frames
    if _camera_queue is None:
        raise RuntimeError("Camera processor is not running")
    dropped = False
    if _camera_queue.full():
        with suppress(asyncio.QueueEmpty):
            _camera_queue.get_nowait()
            _camera_queue.task_done()
            _dropped_stale_frames += 1
            dropped = True
    _camera_queue.put_nowait(job)
    return dropped


async def start_camera_processor() -> None:
    global _camera_queue, _camera_worker_task
    if _camera_worker_task is None or _camera_worker_task.done():
        _camera_queue = asyncio.Queue(maxsize=1)
        _camera_worker_task = asyncio.create_task(_camera_worker(), name="camera-yolo-worker")


async def stop_camera_processor() -> None:
    global _camera_queue, _camera_worker_task
    if _camera_worker_task is None:
        return
    _camera_worker_task.cancel()
    with suppress(asyncio.CancelledError):
        await _camera_worker_task
    _camera_worker_task = None
    _camera_queue = None


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


async def _process_camera_job(job: CameraJob) -> None:
    await wait_for_voice_idle()
    analysis = await asyncio.to_thread(analyze_frame, job.filename)
    with SessionLocal() as db:
        worker = db.get(WorkerState, job.worker_id)
        if worker is None:
            return
        _merge_detection(worker, analysis)
        recalculate_risk(db, worker)

        hazards = analysis.get("hazards") or {}
        evacuation_created = False
        if hazards.get("fire") or hazards.get("large_fire"):
            _, evacuation_created = trigger_fire(
                db,
                "yolo",
                job.worker_id,
                {"analysis": analysis, "filename": job.filename},
            )
        ppe = analysis.get("ppe") or {}
        missing = [name for name, worn in ppe.items() if worn is False]
        severity = "danger" if hazards.get("fire") or hazards.get("smoke") else "warning" if missing else "info"
        image_name = analysis.get("annotated_source") or job.filename
        event = _upsert_camera_event(
            db,
            worker_id=job.worker_id,
            device_id=job.device_id,
            severity=severity,
            details={
                "filename": image_name,
                "raw_filename": job.filename,
                "url": f"/captures/{image_name}",
                "analysis": analysis,
                "helmet_id": job.helmet_id,
                "evacuation_created": evacuation_created,
            },
        )
        db.commit()
        result = event_to_dict(event)
        result["worker"] = worker_to_dict(worker)
        result["evacuation"] = evacuation_snapshot(db)
        if evacuation_created and result["evacuation"]["incident"]:
            route = result["evacuation"]["routes"].get(job.worker_id)
            if route:
                result["helmet_guidance"] = await send_helmet_guidance(
                    job.worker_id,
                    assistant_device_id(db, job.worker_id),
                    result["evacuation"]["incident"]["incident_id"],
                    route,
                    force=True,
                )
    await manager.broadcast("camera_frame", result)


async def _camera_worker() -> None:
    if _camera_queue is None:
        raise RuntimeError("Camera queue was not initialized")
    queue = _camera_queue
    while True:
        job = await queue.get()
        try:
            await _process_camera_job(job)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Camera analysis failed for %s", job.filename)
        finally:
            queue.task_done()


@router.post("/frame", status_code=202)
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
    db.commit()
    dropped_stale = enqueue_camera_job(CameraJob(path.name, device_id, worker_id, helmet_id))
    return {
        "accepted": True,
        "device_id": device_id,
        "filename": path.name,
        "processing": "queued",
        "queue_depth": _camera_queue.qsize() if _camera_queue is not None else 0,
        "dropped_stale": dropped_stale,
    }


@router.get("/processor/status")
def processor_status():
    return {
        "running": _camera_worker_task is not None and not _camera_worker_task.done(),
        "queue_depth": _camera_queue.qsize() if _camera_queue is not None else 0,
        "queue_capacity": _camera_queue.maxsize if _camera_queue is not None else 1,
        "dropped_stale_frames": _dropped_stale_frames,
        "voice_requests_active": voice_requests_active(),
    }


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
