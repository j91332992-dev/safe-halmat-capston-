import json
import math

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db, utcnow
from ..config import settings
from ..models.entities import Anchor, Device, Location, SiteLayout, WorkerState, Zone
from ..schemas.api import UwbDistancesIn
from ..services.event_service import create_event, event_to_dict
from ..services.evacuation_service import calculate_route, current_incident
from ..services.location_filter_service import filter_location, reset_location_filter
from ..services.location_speed_service import speed_guard
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

router = APIRouter(prefix="/api", tags=["uwb"])


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
async def upload_distances(payload: UwbDistancesIn, db: Session = Depends(get_db)):
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
    measured_anchors = db.query(Anchor).filter(Anchor.anchor_id.in_(measured_ids)).all()
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
        create_event(db, "LOCATION_FAILED", str(exc), "warning", payload.worker_id, payload.device_id)
        db.commit()
        return JSONResponse(status_code=422, content={"detail": str(exc),
            "location": {"x": worker.x, "y": worker.y, "confidence": worker.confidence, "changed": False},
            "worker": worker_to_dict(worker), "event": None, "evacuation_route": None,
            "observation": {"measurement_id": payload.measurement_id, "accepted": True,
                            "server_received_at": received_at, "position_accepted": False, "log_saved": saved,
                            "position_check": check, "pipeline": pipeline, "distance_processing": processing}})
    check = speed_guard.check(payload, raw_x, raw_y)
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
    position_changed = abs(x - previous_position[0]) > 0.001 or abs(y - previous_position[1]) > 0.001
    layout = db.get(SiteLayout, settings.site_id)
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
            x=worker.x,
            y=worker.y,
            confidence=confidence,
            distances_json=json.dumps(measurements),
        )
        db.add(location)
    zone_event = None
    for zone in db.query(Zone).filter(Zone.active.is_(True)).all():
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
    incident = current_incident(db)
    route = calculate_route(db, worker, incident) if incident else None
    result = {"location": {"x": worker.x, "y": worker.y, "confidence": confidence, "raw_x": raw_x, "raw_y": raw_y, "changed": position_changed}, "worker": worker_to_dict(worker), "event": event_to_dict(zone_event) if zone_event else None, "evacuation_route": route}
    result["observation"] = {"measurement_id": payload.measurement_id,
                             "server_received_at": received_at, "log_saved": log_saved,
                             "accepted": True, "distance_processing": processing,
                             "position_check": check, "position_accepted": check["accepted"], "pipeline": pipeline}
    if position_changed or zone_event:
        await manager.broadcast("location", result)
    return result


@router.get("/locations/{worker_id}/latest")
def latest_location(worker_id: str, db: Session = Depends(get_db)):
    worker = db.get(WorkerState, worker_id)
    if not worker:
        raise HTTPException(404, "작업자를 찾을 수 없습니다.")
    return worker_to_dict(worker)


@router.get("/locations/{worker_id}/history")
def location_history(worker_id: str, limit: int = 100, db: Session = Depends(get_db)):
    rows = db.query(Location).filter(Location.worker_id == worker_id).order_by(Location.created_at.desc()).limit(min(limit, 10000)).all()
    return [
        {"x": r.x, "y": r.y, "confidence": r.confidence, "created_at": r.created_at.isoformat() + "Z"}
        for r in reversed(rows)
    ]




