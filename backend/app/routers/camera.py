import asyncio
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from contextlib import suppress
from dataclasses import dataclass, field
import ctypes
import json
import logging
import multiprocessing
import os
import secrets
import shutil
import struct
from pathlib import Path
from threading import Lock
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db, utcnow
from ..models.entities import Device, Event, WorkerState
from ..config import settings
from ..services.camera_service import CAPTURE_DIR, latest_raw_frame, latest_preview_frame, remember_raw_frame, save_frame, save_frame_bytes
from ..services.event_service import create_event, event_to_dict
from ..services.device_service import mark_device_seen
from ..services.evacuation_service import evacuation_snapshot, trigger_fire
from ..services.evacuation_guidance_service import assistant_device_id, send_helmet_guidance
from ..services.risk_service import recalculate_risk
from ..services.serializers import worker_to_dict
from ..services.yolo_service import analyze_frame
from ..services.camera_trace import record_analysis
from ..services.detail_merge import merge_detail
from ..services.frame_pacing import next_deadline, inference_interval
from ..services.inference_priority import voice_requests_active
from ..websocket import manager
from .auth import session_identity

router = APIRouter(prefix="/api/camera", tags=["camera"])
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CameraJob:
    filename: str
    device_id: str
    worker_id: str
    helmet_id: str
    frame_id: int | None = None
    queued_at: float = field(default_factory=time.monotonic)


class MockDetectionIn(BaseModel):
    worker_id: str
    device_id: str
    vest: bool | None = None
    glove: bool | None = None
    fire: bool = False
    smoke: bool = False


# Only retain the newest waiting frame. YOLO processes one frame at a time;
# allowing a backlog would make fire/PPE decisions describe old video.
_camera_queue: asyncio.Queue[CameraJob] | None = None
_camera_worker_task: asyncio.Task | None = None
_loop_probe_task: asyncio.Task | None = None
_loop_lag_ms = deque(maxlen=200)
_inference_executor: ProcessPoolExecutor | None = None
_detail_executor: ProcessPoolExecutor | None = None
_detail_task: asyncio.Task | None = None
_detail_cache: dict[str, dict] = {}
_detail_image_cache: dict[str, tuple[bytes, dict]] = {}
_detail_last_submitted: dict[str, float] = {}
_detail_completed = 0
_detail_last_ms = 0.0
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
_fast_gpu_active = False
_analysis_completed = 0
_received_frames = 0
_received_jpeg_bytes = 0
_received_payload_bytes = 0
_last_jpeg_bytes = 0
_last_analysis_started_at = 0.0
_last_postprocess_ms = 0.0
_last_queue_age_ms = 0.0
_paced_skipped_frames = 0
_normal_inference_interval_seconds = 1.0 / settings.yolo_target_fps
_voice_inference_interval_seconds = 1.0


def _initialize_inference_worker(threads: int = 3, lane: str = 'fast') -> None:
    """Reserve CPU headroom for STT/TTS while YOLO continues at low priority."""
    try:
        os.environ['HANMIR_YOLO_CPU_THREADS'] = str(threads)
        os.environ['HANMIR_YOLO_LANE'] = lane
        import torch
        import cv2

        cv2.setNumThreads(1)
        torch.set_num_threads(threads)
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
    global _camera_queue, _camera_worker_task, _inference_executor, _detail_executor, _loop_probe_task
    import cv2
    cv2.setNumThreads(1)
    if _camera_worker_task is None or _camera_worker_task.done():
        _camera_queue = asyncio.Queue(maxsize=1)
        _inference_executor = ProcessPoolExecutor(
            max_workers=1,
            mp_context=multiprocessing.get_context("spawn"),
            initializer=_initialize_inference_worker,
        )
        _camera_worker_task = asyncio.create_task(_camera_worker(), name="camera-yolo-worker")
        _loop_probe_task = asyncio.create_task(_probe_loop_lag(), name="camera-loop-probe")
        if settings.yolo_async_detail:
            _detail_executor = ProcessPoolExecutor(max_workers=1,
                mp_context=multiprocessing.get_context("spawn"),
                initializer=_initialize_inference_worker, initargs=(2,'detail'))


async def _probe_loop_lag():
    while True:
        started=time.monotonic()
        await asyncio.sleep(.05)
        _loop_lag_ms.append(max(0.,(time.monotonic()-started-.05)*1000))


async def stop_camera_processor() -> None:
    global _camera_queue, _camera_worker_task, _inference_executor, _detail_executor, _detail_task, _loop_probe_task
    if _camera_worker_task is None:
        return
    _camera_worker_task.cancel()
    with suppress(asyncio.CancelledError):
        await _camera_worker_task
    _camera_worker_task = None
    if _loop_probe_task is not None:
        _loop_probe_task.cancel()
        with suppress(asyncio.CancelledError):
            await _loop_probe_task
        _loop_probe_task = None
    _camera_queue = None
    if _detail_task is not None:
        _detail_task.cancel()
        with suppress(asyncio.CancelledError):
            await _detail_task
        _detail_task = None
    if _detail_executor is not None:
        _detail_executor.shutdown(wait=False, cancel_futures=True)
        _detail_executor = None
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


async def _run_detail(job: CameraJob, filename: str, submitted_at: float) -> None:
    global _detail_completed, _detail_last_ms
    try:
        started=time.perf_counter()
        analysis=await asyncio.get_running_loop().run_in_executor(_detail_executor, analyze_frame, filename, True)
        _detail_last_ms=(time.perf_counter()-started)*1000
        detail_jpeg = analysis.pop('_annotated_jpeg',None)
        if detail_jpeg:
            with _latest_analysis_lock:
                _detail_image_cache[job.device_id] = (detail_jpeg, dict(frame_id=job.frame_id,
                    analyzed_at=utcnow().isoformat()+'Z', analysis=analysis))
        _detail_completed+=1
        if analysis.get('mode')=='real':
            _detail_cache[job.device_id]=dict(analysis=analysis,frame_id=job.frame_id,submitted_at=submitted_at)
        if settings.yolo_trace_enabled:
            record_analysis(lane='detail',device_id=job.device_id,frame_id=job.frame_id,
                            inference_ms=round(_detail_last_ms,2),analysis=analysis)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception('Separate PPE analysis failed')
    finally:
        with suppress(OSError):
            (CAPTURE_DIR/filename).unlink(missing_ok=True)


async def _process_camera_job(job: CameraJob) -> None:
    global _last_inference_ms, _analysis_completed, _last_analysis_started_at, _detail_task, _fast_gpu_active
    if _inference_executor is None:
        raise RuntimeError("YOLO inference executor is not running")
    _last_analysis_started_at = time.monotonic()
    inference_started = time.perf_counter()
    # Full-frame target stays unchanged during voice. Async detail has its own
    # opt-in voice policy and keeps at most one job in flight.
    detail_enabled = voice_requests_active() == 0 and not settings.yolo_async_detail
    if (settings.yolo_async_detail and _detail_executor is not None and (voice_requests_active()==0 or settings.yolo_detail_during_voice)
            and (_detail_task is None or _detail_task.done())
            and time.monotonic()-_detail_last_submitted.get(job.device_id,0)>=settings.yolo_ppe_detail_interval_seconds):
        # One in-flight detail frame globally; never accumulate old detail jobs.
        detail_name=f'_detail/{Path(job.filename).name}'
        (CAPTURE_DIR/'_detail').mkdir(exist_ok=True)
        shutil.copyfile(CAPTURE_DIR/job.filename,CAPTURE_DIR/detail_name)
        submitted=time.monotonic()
        _detail_last_submitted[job.device_id]=submitted
        _detail_task=asyncio.create_task(_run_detail(job,detail_name,submitted))
    analysis = await asyncio.get_running_loop().run_in_executor(
        _inference_executor, analyze_frame, job.filename, detail_enabled
    )
    _last_inference_ms = (time.perf_counter() - inference_started) * 1000.0
    _analysis_completed += 1
    _fast_gpu_active = analysis.get('engine') == 'openvino_gpu_fp32'
    annotated_jpeg = analysis.pop("_annotated_jpeg", None)
    if settings.yolo_async_detail:
        analysis=merge_detail(analysis,_detail_cache.get(job.device_id),time.monotonic(),settings.yolo_detail_max_age_seconds)
    if settings.yolo_trace_enabled:
        record_analysis(lane='fast',device_id=job.device_id, frame_id=job.frame_id,
                        inference_ms=round(_last_inference_ms, 2),
                        detail_enabled=detail_enabled, target_fps=settings.yolo_target_fps,
                        received_frames=_received_frames, analysis_completed=_analysis_completed,
                        analysis=analysis)
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
        "frame_id": job.frame_id,
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

    result, guidance = await asyncio.to_thread(_persist_camera_analysis, job, analysis, raw_path, annotated_jpeg, cache_details, hazards, missing, hazard_signature, alert_signature, now, alert_due)
    if result is None:
        return
    if guidance:
        result["helmet_guidance"] = await send_helmet_guidance(*guidance, force=True)
    await manager.broadcast("camera_frame", result)


def _persist_camera_analysis(job, analysis, raw_path, annotated_jpeg, cache_details, hazards, missing, hazard_signature, alert_signature, now, alert_due):
    guidance = None
    event: Event | None = None
    evidence_name: str | None = None
    with SessionLocal() as db:
        worker = db.get(WorkerState, job.worker_id)
        if worker is None:
            with suppress(OSError):
                raw_path.unlink(missing_ok=True)
            return None, None
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
        result["evacuation"] = evacuation_snapshot(db, worker.site_id)
        if event and evacuation_created and result["evacuation"]["incident"]:
            route = result["evacuation"]["routes"].get(job.worker_id)
            if route:
                guidance = (job.worker_id, assistant_device_id(db, job.worker_id),
                            result["evacuation"]["incident"]["incident_id"], route)

    # Keep raw evidence only when an alert was actually persisted.
    if not event:
        with suppress(OSError):
            raw_path.unlink(missing_ok=True)
    return result, guidance


async def _camera_worker() -> None:
    global _last_postprocess_ms, _last_queue_age_ms, _paced_skipped_frames
    if _camera_queue is None:
        raise RuntimeError("Camera queue was not initialized")
    queue = _camera_queue
    due = 0.0
    prior_interval = _normal_inference_interval_seconds
    while True:
        job = await queue.get()
        try:
            # Voice no longer lowers the fast-frame FPS target. Replace waiting jobs with the
            # newest frame so YOLO never analyzes a stale backlog.
            while True:
                interval = inference_interval(_normal_inference_interval_seconds,
                    voice_requests_active()>0,_fast_gpu_active,settings.yolo_gpu_voice_fps)
                if interval != prior_interval:
                    due = time.monotonic()
                    prior_interval = interval
                remaining = due - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    newer = await asyncio.wait_for(queue.get(), timeout=remaining)
                except asyncio.TimeoutError:
                    break
                with suppress(OSError):
                    (CAPTURE_DIR / job.filename).unlink(missing_ok=True)
                queue.task_done()
                _paced_skipped_frames += 1
                job = newer
            _last_queue_age_ms = (time.monotonic()-job.queued_at)*1000
            job_started = time.perf_counter()
            due = next_deadline(due, time.monotonic(), interval)
            await _process_camera_job(job)
            job_ms = (time.perf_counter()-job_started)*1000
            _last_postprocess_ms = max(0.0,job_ms-_last_inference_ms)
            if settings.yolo_trace_enabled:
                record_analysis(lane='pipeline',device_id=job.device_id,frame_id=job.frame_id,
                    queue_age_ms=round(_last_queue_age_ms,2),job_ms=round(job_ms,2),
                    postprocess_ms=round(_last_postprocess_ms,2),inference_ms=round(_last_inference_ms,2),
                    voice_active=voice_requests_active(),analysis={})
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Camera analysis failed for %s", job.filename)
        finally:
            queue.task_done()


@router.post("/mock-detection")
async def mock_detection(payload: MockDetectionIn, db: Session = Depends(get_db)):
    """Lightweight camera substitute used when the physical helmet is not wired."""
    device = db.get(Device, payload.device_id)
    worker = db.get(WorkerState, payload.worker_id)
    if not device:
        raise HTTPException(404, "먼저 장치를 등록하세요.")
    if not worker:
        raise HTTPException(404, "작업자를 찾을 수 없습니다.")
    mark_device_seen(device, "camera")
    ppe = json.loads(worker.ppe_json or "{}")
    if payload.vest is not None:
        ppe["vest"] = payload.vest
    if payload.glove is not None:
        ppe["glove"] = payload.glove
    worker.ppe_json = json.dumps(ppe, ensure_ascii=False)
    hazards = json.loads(worker.hazard_json or "{}")
    hazards.update({"fire": payload.fire, "smoke": payload.smoke})
    worker.hazard_json = json.dumps(hazards, ensure_ascii=False)
    recalculate_risk(db, worker)
    db.commit()
    result = {"type": "mock_detection", "worker": worker_to_dict(worker), "device_id": device.device_id}
    await manager.broadcast("camera_mock", result)
    return result


@router.post("/frame", status_code=202)
async def upload_frame(
    file: UploadFile = File(...),
    device_id: str = Form(...),
    worker_id: str = Form(...),
    helmet_id: str = Form("helmet-001"),
    frame_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
):
    device = db.get(Device, device_id)
    worker = db.get(WorkerState, worker_id)
    if not device:
        raise HTTPException(404, "먼저 장치를 등록하세요.")
    if not worker:
        raise HTTPException(404, "작업자를 찾을 수 없습니다.")
    path = await save_frame(file, device_id)
    await asyncio.to_thread(remember_raw_frame, device_id, path.read_bytes(), frame_id)
    global _received_frames
    global _received_jpeg_bytes, _received_payload_bytes, _last_jpeg_bytes
    _last_jpeg_bytes=path.stat().st_size
    _received_jpeg_bytes+=_last_jpeg_bytes
    _received_payload_bytes+=_last_jpeg_bytes
    _received_frames += 1
    now = time.monotonic()
    if now - _last_device_seen_commit.get(device_id, 0.0) >= 1.0:
        mark_device_seen(device, "camera")
        db.commit()
        _last_device_seen_commit[device_id] = now
    relative_name = path.relative_to(CAPTURE_DIR).as_posix()
    dropped_stale = enqueue_camera_job(CameraJob(relative_name, device_id, worker_id, helmet_id, frame_id))
    return {
        "accepted": True,
        "device_id": device_id,
        "filename": relative_name,
        "processing": "queued",
        "queue_depth": _camera_queue.qsize() if _camera_queue is not None else 0,
        "dropped_stale": dropped_stale,
        "frame_id": frame_id,
    }


def _store_received_frame(jpeg, device_id, frame_id):
    path=save_frame_bytes(jpeg,device_id)
    remember_raw_frame(device_id,jpeg,frame_id)
    return path


def _touch_camera_device(device_id):
    with SessionLocal() as db:
        current=db.get(Device,device_id)
        if current is not None:
            mark_device_seen(current,'camera')
            db.commit()


@router.websocket("/stream/{device_id}")
async def stream_frames(websocket: WebSocket, device_id: str, worker_id: str, helmet_id: str = "helmet-001"):
    """P4 v1: one binary message = 16-byte header + complete JPEG.

    Header: ASCII HMR2, uint64 frame ID, uint16 width, uint16 height,
    all integers big-endian. The secret is required; S3 multipart is unchanged.
    """
    token = websocket.headers.get("x-hanmir-camera-token", "")
    if not settings.camera_ingest_token or not secrets.compare_digest(token, settings.camera_ingest_token):
        await websocket.close(code=1008, reason="camera token required")
        return
    with SessionLocal() as db:
        device = db.get(Device, device_id)
        worker = db.get(WorkerState, worker_id)
        if device is None or worker is None or device.worker_id != worker_id:
            await websocket.close(code=1008, reason="unknown device or worker")
            return
    await websocket.accept()
    last_frame_id = -1
    accepted = 0
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            packet = message.get("bytes")
            if packet is None:
                await websocket.close(code=1003, reason="binary frames only")
                break
            if len(packet) < 20 or len(packet) > settings.camera_max_frame_bytes + 16:
                await websocket.close(code=1009, reason="invalid frame length")
                break
            magic, frame_id, width, height = struct.unpack(">4sQHH", packet[:16])
            jpeg = packet[16:]
            if (magic != b"HMR2" or frame_id <= last_frame_id or not 0 < width <= 4096
                    or not 0 < height <= 4096 or not jpeg.startswith(b"\xff\xd8")
                    or not jpeg.endswith(b"\xff\xd9")):
                await websocket.close(code=1003, reason="invalid JPEG or frame header")
                break
            last_frame_id = frame_id
            global _received_jpeg_bytes, _received_payload_bytes, _last_jpeg_bytes
            _last_jpeg_bytes=len(jpeg)
            _received_jpeg_bytes+=len(jpeg)
            _received_payload_bytes+=len(packet)
            path = await asyncio.to_thread(_store_received_frame, jpeg, device_id, frame_id)
            relative_name = path.relative_to(CAPTURE_DIR).as_posix()
            dropped = enqueue_camera_job(CameraJob(relative_name, device_id, worker_id, helmet_id, frame_id))
            global _received_frames
            _received_frames += 1
            accepted += 1
            if accepted == 1 or accepted % 8 == 0:
                await asyncio.to_thread(_touch_camera_device, device_id)
                await websocket.send_json({"type": "frame_ack", "frame_id": frame_id,
                                           "queue_depth": _camera_queue.qsize() if _camera_queue else 0,
                                           "dropped_stale": dropped})
    except WebSocketDisconnect:
        pass


@router.get("/processor/status")
def processor_status():
    from ..services.audio_service import upload_stats
    lag=sorted(list(_loop_lag_ms))
    return {
        "event_loop_lag_ms": {"samples":len(lag), "p50":round(lag[len(lag)//2],2) if lag else None,
            "p95":round(lag[min(len(lag)-1,int(len(lag)*.95))],2) if lag else None,
            "max":round(max(lag),2) if lag else None},
        "sampled_at_seconds": time.monotonic(),
        "audio_upload": upload_stats(),
        "running": _camera_worker_task is not None and not _camera_worker_task.done(),
        "queue_depth": _camera_queue.qsize() if _camera_queue is not None else 0,
        "queue_capacity": _camera_queue.maxsize if _camera_queue is not None else 1,
        "dropped_stale_frames": _dropped_stale_frames,
        "voice_requests_active": voice_requests_active(),
        "fast_gpu_active": _fast_gpu_active,
        "voice_target_fps": settings.yolo_target_fps,
        "received_jpeg_bytes": _received_jpeg_bytes,
        "received_payload_bytes": _received_payload_bytes,
        "last_jpeg_bytes": _last_jpeg_bytes,
        "last_inference_ms": round(_last_inference_ms, 1),
        "analysis_completed": _analysis_completed,
        "target_inference_fps": 1.0 / _normal_inference_interval_seconds,
        "received_frames": _received_frames,
        "paced_skipped_frames": _paced_skipped_frames,
        "last_postprocess_ms": round(_last_postprocess_ms,1),
        "last_queue_age_ms": round(_last_queue_age_ms,1),
        "detail_completed": _detail_completed,
        "detail_last_ms": round(_detail_last_ms,1),
        "detail_busy": _detail_task is not None and not _detail_task.done(),
        "detail_separated": settings.yolo_async_detail,
        "brightness_gamma": settings.camera_display_gamma,
        "preview_gamma": settings.camera_preview_gamma or settings.camera_display_gamma,
        "preview_red_gain": settings.camera_preview_red_gain,
        "preview_blue_gain": settings.camera_preview_blue_gain,
        "sharpen_amount": settings.camera_sharpen_amount,
        "head_tight_probe": settings.yolo_head_tight_probe,
        "inference_process_isolated": _inference_executor is not None,
    }


@router.get("/{device_id}/live")
def latest_raw_status(device_id: str):
    raw = latest_raw_frame(device_id)
    if raw is None:
        return {"device_id": device_id, "received": False}
    _, metadata = raw
    return {"device_id": device_id, "received": True,
            "frame_id": metadata["frame_id"],
            "age_ms": round((time.monotonic() - metadata["received_monotonic"]) * 1000)}


@router.get("/{device_id}/live/image")
def latest_raw_image(device_id: str, corrected: bool = False):
    raw = latest_preview_frame(device_id) if corrected else latest_raw_frame(device_id)
    if raw is None:
        raise HTTPException(404, "수신된 원본 카메라 프레임이 없습니다.")
    return Response(content=raw[0], media_type="image/jpeg",
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@router.get("/{device_id}/live/mjpeg")
async def raw_live_stream(device_id: str, request: Request, token: str = ""):
    identity = session_identity(request.headers.get("authorization") or f"Bearer {token}")
    if identity.get("role") == "worker":
        raise HTTPException(403, "관리자 권한이 필요합니다.")
    with SessionLocal() as db:
        device = db.get(Device, device_id)
        if not device or device.site_id != identity.get("site_id"):
            raise HTTPException(404, "장치를 찾을 수 없습니다.")
    async def frames():
        previous = None
        while not await request.is_disconnected():
            raw = latest_preview_frame(device_id)
            if raw is not None:
                jpeg, metadata = raw
                token = metadata["received_monotonic"]
                if token != previous and time.monotonic() - token < 3:
                    previous = token
                    yield (b"--hanmirframe\r\nContent-Type: image/jpeg\r\nContent-Length: "
                           + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")
            # Preview the newest frame only; slow viewers never create a backlog.
            await asyncio.sleep(1 / 15)
    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=hanmirframe",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@router.get("/{device_id}/latest")
def latest_frame(device_id: str, detailed: bool = False, metadata_only: bool = False, db: Session = Depends(get_db)):
    with _latest_analysis_lock:
        cached = (_detail_image_cache if detailed else _latest_analysis_cache).get(device_id)
        cached_details = dict(cached[1]) if cached else None
    if cached_details is not None:
        if metadata_only:
            cached_details = {k:cached_details[k] for k in ("frame_id", "analyzed_at", "filename") if k in cached_details}
        return {"device_id": device_id, "received": True, **cached_details}
    if detailed:
        return {"device_id": device_id, "received": False}
    event = (
        db.query(Event)
        .filter(Event.device_id == device_id, Event.event_type == "CAMERA_FRAME")
        .order_by(Event.created_at.desc())
        .first()
    )
    if not event:
        return {"device_id": device_id, "received": False}
    details = json.loads(event.details_json)
    filename = details.get("filename")
    if not filename or not (CAPTURE_DIR / str(filename)).is_file():
        return {"device_id": device_id, "received": False}
    return {"device_id": device_id, "received": True, "analyzed_at": event.created_at.isoformat() + "Z", **details}


@router.get("/{device_id}/latest/image")
def latest_frame_image(device_id: str, detailed: bool = False, db: Session = Depends(get_db)):
    with _latest_analysis_lock:
        cached = (_detail_image_cache if detailed else _latest_analysis_cache).get(device_id)
        cached_image = cached[0] if cached else None
    if cached_image is not None:
        return Response(
            content=cached_image,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"},
        )
    if detailed:
        raise HTTPException(404, "Detailed analysis pending")
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
    if not filepath.is_file():
        raise HTTPException(404, "이미지 파일을 찾을 수 없습니다.")
    return FileResponse(
        filepath,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"},
    )
