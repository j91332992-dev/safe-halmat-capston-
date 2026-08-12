import asyncio
from concurrent.futures import ProcessPoolExecutor
from contextlib import suppress
from dataclasses import dataclass
import ctypes
import json
import logging
import multiprocessing
import os
from pathlib import Path
from threading import Lock
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
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
from ..services.inference_priority import voice_requests_active
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
_inference_executor: ProcessPoolExecutor | None = None
_dropped_stale_frames = 0
_latest_analysis_cache: dict[str, tuple[bytes, dict]] = {}
_latest_analysis_lock = Lock()
_last_checkpoint_at: dict[str, float] = {}
_last_alert_at: dict[str, float] = {}
_last_alert_signature: dict[str, tuple] = {}
_last_device_seen_commit: dict[str, float] = {}
_checkpoint_interval_seconds = 1.0
_alert_refresh_seconds = 5.0
_last_inference_ms = 0.0
_analysis_completed = 0
_last_analysis_started_at = 0.0
_normal_inference_interval_seconds = 1.0 / 4.0
_voice_inference_interval_seconds = 1.0


def _initialize_inference_worker() -> None:
    """Reserve CPU headroom for STT/TTS while YOLO continues at low priority."""
    try:
        import torch

        torch.set_num_threads(3)
        torch.set_num_interop_threads(1)
    except Exception:
        logger.exception("Could not limit YOLO worker threads")
    if os.name == "nt":
        # BELOW_NORMAL_PRIORITY_CLASS. Audio remains in the normal-priority
        # backend and therefore wins CPU scheduling contention.
        with suppress(Exception):
            ctypes.windll.kernel32.SetPriorityClass(
                ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000
            )


def enqueue_camera_job(job: CameraJob) -> bool:
    """Queue the newest frame and return True when an older queued frame was dropped."""
    global _dropped_stale_frames
    if _camera_queue is None:
        raise RuntimeError("Camera processor is not running")
    dropped = False
    if _camera_queue.full():
        with suppress(asyncio.QueueEmpty):
            stale = _camera_queue.get_nowait()
            _camera_queue.task_done()
            _dropped_stale_frames += 1
            dropped = True
            with suppress(OSError):
                (CAPTURE_DIR / stale.filename).unlink(missing_ok=True)
    _camera_queue.put_nowait(job)
    return dropped


async def start_camera_processor() -> None:
    global _camera_queue, _camera_worker_task, _inference_executor
    if _camera_worker_task is None or _camera_worker_task.done():
        _camera_queue = asyncio.Queue(maxsize=1)
        _inference_executor = ProcessPoolExecutor(
            max_workers=1,
            mp_context=multiprocessing.get_context("spawn"),
            initializer=_initialize_inference_worker,
        )
        _camera_worker_task = asyncio.create_task(_camera_worker(), name="camera-yolo-worker")


async def stop_camera_processor() -> None:
    global _camera_queue, _camera_worker_task, _inference_executor
    if _camera_worker_task is None:
        return
    _camera_worker_task.cancel()
    with suppress(asyncio.CancelledError):
        await _camera_worker_task
    _camera_worker_task = None
    _camera_queue = None
    if _inference_executor is not None:
        _inference_executor.shutdown(wait=False, cancel_futures=True)
        _inference_executor = None


def _upsert_camera_event(
    db: Session,
    *,
    worker_id: str,
    device_id: str,
    severity: str,
    details: dict,
    message: str,
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
            message,
            severity,
            worker_id=worker_id,
            device_id=device_id,
            details=details,
        )
    event.worker_id = worker_id
    event.severity = severity
    event.status = "open"
    event.message = message
    event.details_json = json.dumps(details, ensure_ascii=False)
    event.created_at = utcnow()
    return event


def _merge_detection(worker: WorkerState, analysis: dict) -> None:
    if analysis.get("mode") != "real":
        return
    current_hazards = json.loads(worker.hazard_json or "{}")
    current_hazards.update(analysis.get("hazards") or {})
    observed_ppe = analysis.get("ppe") or {}
    current_hazards["ppe_subject_scope"] = "observed_person"
    current_hazards["observed_person_seen"] = bool(analysis.get("person_seen"))
    current_hazards["observed_person_ppe"] = observed_ppe
    current_hazards["observed_person_missing_ppe"] = [name for name, worn in observed_ppe.items() if worn is False]
    current_hazards["observed_person_ppe_judgement"] = analysis.get("ppe_judgement") or {}
    worker.hazard_json = json.dumps(current_hazards, ensure_ascii=False)


async def _process_camera_job(job: CameraJob) -> None:
    global _last_inference_ms, _analysis_completed, _last_analysis_started_at
    if _inference_executor is None:
        raise RuntimeError("YOLO inference executor is not running")
    _last_analysis_started_at = time.monotonic()
    inference_started = time.perf_counter()
    # Voice/STT always wins CPU time. Keep a lightweight full-frame pass at
    # 1 FPS during speech and disable the extra 640px person-crop inference.
    detail_enabled = voice_requests_active() == 0
    analysis = await asyncio.get_running_loop().run_in_executor(
        _inference_executor, analyze_frame, job.filename, detail_enabled
    )
    _last_inference_ms = (time.perf_counter() - inference_started) * 1000.0
    _analysis_completed += 1
    annotated_jpeg = analysis.pop("_annotated_jpeg", None)
    raw_path = CAPTURE_DIR / job.filename
    if not annotated_jpeg:
        with suppress(OSError):
            annotated_jpeg = raw_path.read_bytes()

    cache_details = {
        "filename": job.filename,
        "raw_filename": job.filename,
        "url": f"/api/camera/{job.device_id}/latest/image",
        "analysis": analysis,
        "helmet_id": job.helmet_id,
        "analyzed_at": utcnow().isoformat() + "Z",
    }
    if annotated_jpeg:
        with _latest_analysis_lock:
            _latest_analysis_cache[job.device_id] = (annotated_jpeg, cache_details)

    hazards = analysis.get("hazards") or {}
    ppe = analysis.get("ppe") or {}
    missing = tuple(sorted(name for name, worn in ppe.items() if worn is False))
    hazard_signature = tuple(
        bool(hazards.get(name)) for name in ("fire", "large_fire", "smoke", "fallen")
    )
    alert_signature = hazard_signature + missing
    dangerous = any(hazard_signature) or bool(missing)
    now = time.monotonic()
    checkpoint_due = now - _last_checkpoint_at.get(job.device_id, 0.0) >= _checkpoint_interval_seconds
    alert_due = dangerous and (
        _last_alert_signature.get(job.device_id) != alert_signature
        or now - _last_alert_at.get(job.device_id, 0.0) >= _alert_refresh_seconds
    )

    # The live analysis view is already updated from memory above. Normal
    # frames only checkpoint worker state once per second; this removes the
    # per-frame event/image/commit work from the YOLO critical path.
    if not checkpoint_due and not alert_due:
        with suppress(OSError):
            raw_path.unlink(missing_ok=True)
        return

    event: Event | None = None
    evidence_name: str | None = None
    with SessionLocal() as db:
        worker = db.get(WorkerState, job.worker_id)
        if worker is None:
            with suppress(OSError):
                raw_path.unlink(missing_ok=True)
            return
        _merge_detection(worker, analysis)
        recalculate_risk(db, worker)

        evacuation_created = False
        if hazards.get("fire") or hazards.get("large_fire"):
            _, evacuation_created = trigger_fire(
                db,
                "yolo",
                job.worker_id,
                {"analysis": analysis, "filename": job.filename},
            )
        if alert_due:
            evidence_name = f"{Path(job.filename).stem}_annotated.jpg"
            raw_evidence_name = f"{Path(job.filename).stem}_raw.jpg"
            if annotated_jpeg:
                (CAPTURE_DIR / evidence_name).write_bytes(annotated_jpeg)
            else:
                evidence_name = job.filename
            if raw_path.exists():
                raw_path.replace(CAPTURE_DIR / raw_evidence_name)
            else:
                raw_evidence_name = job.filename
            severity = "danger" if any(hazard_signature) else "warning"
            ppe_labels = {"helmet": "안전모", "vest": "안전조끼", "glove": "안전장갑"}
            message = (
                "전방 작업자 안전장비 미착용 감지: " + ", ".join(ppe_labels.get(name, name) for name in missing)
                if missing and not any(hazard_signature)
                else "카메라 위험상황 분석 결과를 수신했습니다."
            )
            event = _upsert_camera_event(
                db,
                worker_id=job.worker_id,
                device_id=job.device_id,
                severity=severity,
                message=message,
                details={
                    "filename": evidence_name,
                    "raw_filename": raw_evidence_name,
                    "url": f"/captures/{evidence_name}",
                    "analysis": analysis,
                    "helmet_id": job.helmet_id,
                    "evacuation_created": evacuation_created,
                    "subject_scope": "observed_person",
                    "subject_label": "안전모 착용자가 바라보는 전방 작업자",
                    "missing_ppe": list(missing),
                },
            )
        db.commit()
        _last_checkpoint_at[job.device_id] = now
        if alert_due:
            _last_alert_at[job.device_id] = now
            _last_alert_signature[job.device_id] = alert_signature

        result = event_to_dict(event) if event else {
            "event_type": "CAMERA_ANALYSIS",
            "device_id": job.device_id,
            "worker_id": job.worker_id,
            "details": cache_details,
        }
        result["worker"] = worker_to_dict(worker)
        result["evacuation"] = evacuation_snapshot(db)
        if event and evacuation_created and result["evacuation"]["incident"]:
            route = result["evacuation"]["routes"].get(job.worker_id)
            if route:
                result["helmet_guidance"] = await send_helmet_guidance(
                    job.worker_id,
                    assistant_device_id(db, job.worker_id),
                    result["evacuation"]["incident"]["incident_id"],
                    route,
                    force=True,
                )
    # Keep raw evidence only when an alert was actually persisted.
    if not event:
        with suppress(OSError):
            raw_path.unlink(missing_ok=True)
    await manager.broadcast("camera_frame", result)


async def _camera_worker() -> None:
    if _camera_queue is None:
        raise RuntimeError("Camera queue was not initialized")
    queue = _camera_queue
    while True:
        job = await queue.get()
        try:
            # Pace normal analysis at 4 FPS and all server-side voice work at
            # 1 FPS. While waiting, continuously replace this job with the
            # newest frame so YOLO never analyzes a stale backlog.
            while True:
                interval = (
                    _voice_inference_interval_seconds
                    if voice_requests_active() > 0
                    else _normal_inference_interval_seconds
                )
                remaining = interval - (time.monotonic() - _last_analysis_started_at)
                if remaining <= 0:
                    break
                try:
                    newer = await asyncio.wait_for(queue.get(), timeout=remaining)
                except asyncio.TimeoutError:
                    break
                with suppress(OSError):
                    (CAPTURE_DIR / job.filename).unlink(missing_ok=True)
                queue.task_done()
                job = newer
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
    now = time.monotonic()
    if now - _last_device_seen_commit.get(device_id, 0.0) >= 1.0:
        mark_device_seen(device, "camera")
        db.commit()
        _last_device_seen_commit[device_id] = now
    relative_name = path.relative_to(CAPTURE_DIR).as_posix()
    dropped_stale = enqueue_camera_job(CameraJob(relative_name, device_id, worker_id, helmet_id))
    return {
        "accepted": True,
        "device_id": device_id,
        "filename": relative_name,
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
        "last_inference_ms": round(_last_inference_ms, 1),
        "analysis_completed": _analysis_completed,
        "target_inference_fps": 3,
        "inference_process_isolated": _inference_executor is not None,
    }


@router.get("/{device_id}/latest")
def latest_frame(device_id: str, db: Session = Depends(get_db)):
    with _latest_analysis_lock:
        cached = _latest_analysis_cache.get(device_id)
        cached_details = dict(cached[1]) if cached else None
    if cached_details is not None:
        return {"device_id": device_id, "received": True, **cached_details}
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
    with _latest_analysis_lock:
        cached = _latest_analysis_cache.get(device_id)
        cached_image = cached[0] if cached else None
    if cached_image is not None:
        return Response(
            content=cached_image,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"},
        )
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
