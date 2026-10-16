import json
import math
import asyncio
import time

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from ..database import get_db, utcnow, SessionLocal, engine
from ..config import settings
from ..models.entities import Anchor, Device, Location, SiteLayout, WorkerState, Zone
from ..schemas.api import UwbDistancesIn
from ..services.event_service import create_event, event_to_dict
from ..services.evacuation_service import calculate_route, current_incident
from ..services.location_filter_service import filter_location, reset_location_filter, location_motion_status
from ..services.location_speed_service import speed_guard
from ..services.anchor_transition_guard import anchor_transition_guard
from ..services.device_service import mark_device_seen
from ..services.presence_service import refresh_presence
from ..services.location_service import solve_position
from ..services.risk_service import recalculate_risk
from ..services.serializers import worker_to_dict
from ..site_profile import clamp_position
from ..services.uwb_distance_filter import DistanceFilter
from ..services.uwb_log_service import record_observation
from ..services.zone_service import confirm_zone, point_in_zone
from ..websocket import manager
from .auth import require_site

router = APIRouter(prefix="/api", tags=["uwb"])
_distance_processing_lock = asyncio.Lock()
_failure_notices: dict[tuple[str, str, str], float] = {}


def touch_uwb_device(db, payload):
    device = db.get(Device, payload.device_id)
    if not device:
        device = Device(device_id=payload.device_id, device_type="position_device",
                        organization_id=payload.organization_id, site_id=payload.site_id,
                        worker_id=payload.worker_id, helmet_id=payload.helmet_id)
        db.add(device)
    mark_device_seen(device, "uwb")


def save_position_status(worker, check, received_at):
    worker.position_status_json = json.dumps({**check, "server_received_at": received_at})
    if check["accepted"]:
        # Also advances for a valid stationary candidate whose screen marker holds.
        worker.last_valid_location_at = utcnow()


@router.post("/uwb/distances")
async def upload_distances(payload: UwbDistancesIn, compact_ack: bool = False):
    # Keep stateful range filtering ordered, but never block camera/audio's loop
    # with synchronous SQL or position calculations. The session lives in one thread.
    async with _distance_processing_lock:
        result = await asyncio.to_thread(_distance_session, payload)
        if not isinstance(result, dict):
            return result
        broadcast = result.pop('_broadcast_location', False)
        if broadcast:
            await manager.broadcast('location', result)
        # Device telemetry needs acknowledgement only; retain full server logs.
        return Response(status_code=204) if compact_ack else result


def _distance_session(payload):
    # Keep one connection through commit + response serialization, instead of
    # reopening SQLite for the read following commit. It remains thread-local.
    with engine.connect() as connection:
        with SessionLocal(bind=connection) as db:
            return _process_distances(payload, db)


def _process_distances(payload: UwbDistancesIn, db: Session):
    received_at = utcnow().isoformat() + "Z"
    observation = {"event": "server_cycle", "server_received_at": received_at,
                   "input": payload.model_dump(mode="json"), "candidate_position": None,
                   "filtered_position": None, "final_position": None}
    pipeline = {"communication_received": True, "frame_accepted": False, "distance_usable": False,
                "usable_anchor_count": 0, "position_solved": False, "position_accepted": False, "position_applied": False}
    observation["pipeline"] = pipeline
    worker = db.get(WorkerState, payload.worker_id)
    if not worker:
        observation.update(status="failed", reason="unknown_worker")
        record_observation(observation)
        raise HTTPException(404, "작업자를 찾을 수 없습니다.")
    # Worker/device registration determines the effective site for legacy tags.
    # Keep P4 multi-site isolation when using the incoming shared filter state.
    device = db.get(Device, payload.device_id)
    if device and device.site_id != worker.site_id:
        raise HTTPException(409, "장치와 작업자의 현장이 일치하지 않습니다.")
    payload = payload.model_copy(update={
        "site_id": worker.site_id,
        "organization_id": device.organization_id if device else payload.organization_id,
    })
    observation["effective_site_id"] = payload.site_id
    refresh_presence(db)
    touch_uwb_device(db, payload)
    processing = DistanceFilter(settings).process(payload)
    observation["distance_processing"] = processing
    pipeline["frame_accepted"] = processing["accepted"]
    if not processing["accepted"]:
        observation.update(status="ignored", reason=processing["reason"],
                           final_position={"x": worker.x, "y": worker.y})
        saved = record_observation(observation)
        db.commit()
        return {"location": {"x": worker.x, "y": worker.y, "changed": False},
                "worker": worker_to_dict(worker),
                "observation": {"measurement_id": payload.measurement_id, "server_received_at": received_at,
                                "log_saved": saved, "accepted": False, "reason": processing["reason"], "pipeline": pipeline}}
    measurements = processing["measurements"]
    # Response reception and permission to use its range are separate states.
    measured_ids = ({item.anchor_id for item in payload.observations if item.status != "missing"} |
                    {item.anchor_id for item in payload.measurements if not item.held})
    measured_anchors = db.query(Anchor).filter(Anchor.anchor_id.in_(measured_ids), Anchor.site_id == worker.site_id).all()
    seen_at = utcnow()
    for anchor in measured_anchors:
        anchor.online = True
        anchor.last_seen = seen_at
    anchors = [{"anchor_id": item.anchor_id, "x": item.x, "y": item.y} for item in measured_anchors]
    usable_ids = {m["anchor_id"] for m in measurements} & {a["anchor_id"] for a in anchors}
    pipeline.update(distance_usable=bool(usable_ids), usable_anchor_count=len(usable_ids))
    quality_status = {**processing["quality_summary"], "used_anchor_count": len(usable_ids)}
    observation.update(processed_measurements=measurements, anchors=anchors,
                       previous_position={"x": worker.x, "y": worker.y})
    try:
        raw_x, raw_y, confidence = solve_position(anchors, measurements)
    except ValueError as exc:
        check = {"mode": settings.uwb_speed_mode, "accepted": False, "applied": False,
                 "reason": getattr(exc, "reason", "solve_failed"), "quality_status": quality_status,
                 "solver_diagnostics": getattr(exc, "diagnostics", {})}
        save_position_status(worker, check, received_at)
        observation.update(status="failed", reason=str(exc),
                           position_check=check, position_status=worker_to_dict(worker)["position_status"],
                           final_position={"x": worker.x, "y": worker.y})
        saved = record_observation(observation)
        # Preserve each failed cycle in JSONL; bound identical UI events.
        notice_key = (payload.site_id, payload.worker_id, str(exc))
        notice_now = time.monotonic()
        if notice_now - _failure_notices.get(notice_key, float('-inf')) >= 5:
            create_event(db, "LOCATION_FAILED", str(exc), "warning", payload.worker_id, payload.device_id)
            if len(_failure_notices) >= 1000:
                _failure_notices.pop(min(_failure_notices, key=_failure_notices.get))
            _failure_notices[notice_key] = notice_now
        db.commit()
        return JSONResponse(status_code=422, content={"detail": str(exc),
            "location": {"x": worker.x, "y": worker.y, "confidence": worker.confidence, "changed": False},
            "worker": worker_to_dict(worker), "event": None, "evacuation_route": None,
            "observation": {"measurement_id": payload.measurement_id, "accepted": True,
                            "server_received_at": received_at, "position_accepted": False, "log_saved": saved,
                            "position_check": check, "pipeline": pipeline, "distance_processing": processing}})
    transition = anchor_transition_guard.check(
        (payload.site_id, payload.worker_id, payload.device_id), payload.session_id,
        usable_ids, raw_x, raw_y)
    observation['anchor_transition'] = transition
    if transition['accepted']:
        check = speed_guard.check(payload, raw_x, raw_y)
    else:
        check = dict(mode='enforce', accepted=False, applied=False,
                     reason='anchor_set_change_pending', reset_smoothing=False)
    check['anchor_transition'] = transition
    check["quality_status"] = quality_status
    pipeline.update(position_solved=all(math.isfinite(v) for v in (raw_x, raw_y, confidence)),
                    position_accepted=check["accepted"], position_applied=check["applied"])
    save_position_status(worker, check, received_at)
    candidate = {"x": raw_x if math.isfinite(raw_x) else None, "y": raw_y if math.isfinite(raw_y) else None}
    observation.update(candidate_position=candidate, position_check=check,
                       position_status=worker_to_dict(worker)["position_status"])
    if not check["applied"]:
        # Distance history has already advanced; coordinate/zone state must not.
        observation.update(status="position_rejected", reason=check["reason"],
                           final_position={"x": worker.x, "y": worker.y}, position_changed=False)
        db.commit()
        saved = record_observation(observation)
        return {"location": {"x": worker.x, "y": worker.y, "confidence": worker.confidence,
                             "raw_x": candidate["x"], "raw_y": candidate["y"], "changed": False},
                "worker": worker_to_dict(worker), "event": None, "evacuation_route": None,
                "observation": {"measurement_id": payload.measurement_id, "server_received_at": received_at,
                                "log_saved": saved, "accepted": True, "distance_processing": processing,
                                "position_check": check, "position_accepted": False, "pipeline": pipeline}}
    previous_position = (worker.x, worker.y)
    if check["reset_smoothing"]:
        reset_location_filter(payload.worker_id)
    x, y = filter_location(payload.worker_id, raw_x, raw_y, None if check["reset_smoothing"] else previous_position)
    observation["motion_filter"] = location_motion_status(payload.worker_id)
    position_changed = abs(x - previous_position[0]) > 0.001 or abs(y - previous_position[1]) > 0.001
    layout = db.get(SiteLayout, worker.site_id)
    worker.x, worker.y = clamp_position(x, y, layout.width if layout else None, layout.height if layout else None)
    worker.confidence = confidence
    if check["accepted"]:
        worker.last_valid_location_json = json.dumps({"x": worker.x, "y": worker.y, "confidence": worker.confidence})
    observation["position_status"] = worker_to_dict(worker)["position_status"]
    observation.update(status="computed", candidate_position={"x": raw_x, "y": raw_y},
                       filtered_position={"x": x, "y": y},
                       final_position={"x": worker.x, "y": worker.y},
                       confidence=confidence, position_changed=position_changed)
    if position_changed:
        location = Location(
            worker_id=payload.worker_id,
            site_id=worker.site_id,
            x=worker.x,
            y=worker.y,
            confidence=confidence,
            distances_json=json.dumps(measurements),
        )
        db.add(location)
    zone_event = None
    for zone in db.query(Zone).filter(Zone.site_id == worker.site_id, Zone.active.is_(True)).all():
        allowed_worker_ids = json.loads(zone.allowed_worker_ids_json)
        if payload.worker_id in allowed_worker_ids:
            if worker.current_zone == zone.zone_id:
                worker.current_zone = None
            continue
        is_current = worker.current_zone == zone.zone_id
        confirmed, transition = confirm_zone(payload.worker_id, zone, point_in_zone(worker.x, worker.y, zone), is_current)
        if transition == "ZONE_ENTERED":
            worker.current_zone = zone.zone_id
            zone_event = create_event(db, "DANGER_ZONE_ENTERED", zone.warning_message, "danger", payload.worker_id, payload.device_id, {"zone_id": zone.zone_id})
            break
        if transition == "ZONE_EXITED":
            worker.current_zone = None
            zone_event = create_event(db, "ZONE_EXITED", f"{zone.zone_name}에서 이탈했습니다.", "info", payload.worker_id, payload.device_id, {"zone_id": zone.zone_id})
    recalculate_risk(db, worker)
    db.commit()
    log_saved = record_observation(observation)
    from ..services.evacuation_navigation import latest_route
    route = latest_route(worker.worker_id)
    result = {"location": {"x": worker.x, "y": worker.y, "confidence": confidence, "raw_x": raw_x, "raw_y": raw_y, "changed": position_changed}, "worker": worker_to_dict(worker), "event": event_to_dict(zone_event) if zone_event else None, "evacuation_route": route}
    result["observation"] = {"measurement_id": payload.measurement_id,
                             "server_received_at": received_at, "log_saved": log_saved,
                             "accepted": True, "distance_processing": processing,
                             "position_check": check, "position_accepted": check["accepted"], "pipeline": pipeline}
    result['_broadcast_location'] = bool(position_changed or zone_event)
    return result


@router.get("/locations/{worker_id}/latest")
def latest_location(worker_id: str, site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    worker = db.query(WorkerState).filter(WorkerState.worker_id == worker_id, WorkerState.site_id == site_id).first()
    if not worker:
        raise HTTPException(404, "작업자를 찾을 수 없습니다.")
    return worker_to_dict(worker)


@router.get("/locations/{worker_id}/history")
def location_history(worker_id: str, limit: int = 100, site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    rows = db.query(Location).filter(Location.worker_id == worker_id, Location.site_id == site_id).order_by(Location.created_at.desc()).limit(min(limit, 10000)).all()
    return [
        {"x": r.x, "y": r.y, "confidence": r.confidence, "created_at": r.created_at.isoformat() + "Z"}
        for r in reversed(rows)
    ]






@router.websocket("/uwb/stream")
async def uwb_stream(socket: WebSocket):
    """Persistent telemetry; process in order with the same filters and logs."""
    from pydantic import ValidationError
    await socket.accept()
    try:
        while True:
            raw = await socket.receive_text()
            if len(raw) > 32768:
                await socket.close(code=1009)
                return
            try:
                payload = UwbDistancesIn.model_validate_json(raw)
            except ValidationError:
                await socket.close(code=1008)
                return
            try:
                result = await upload_distances(payload)
                status = result.status_code if isinstance(result, JSONResponse) else 200
            except HTTPException as exc:
                status = exc.status_code
            await socket.send_text(f"ack:{payload.cycle_id}:{status}")
    except WebSocketDisconnect:
        pass
