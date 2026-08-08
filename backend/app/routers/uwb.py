import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db, utcnow
from ..config import settings
from ..models.entities import Anchor, Device, Location, SiteLayout, WorkerState, Zone
from ..schemas.api import UwbDistancesIn
from ..services.event_service import create_event, event_to_dict
from ..services.evacuation_service import calculate_route, current_incident
from ..services.location_filter_service import filter_location
from ..services.device_service import mark_device_seen
from ..services.presence_service import refresh_presence
from ..services.location_service import solve_position
from ..services.risk_service import recalculate_risk
from ..services.serializers import worker_to_dict
from ..site_profile import clamp_position
from ..services.uwb_service import measurements_to_dict
from ..services.zone_service import confirm_zone, point_in_zone
from ..websocket import manager

router = APIRouter(prefix="/api", tags=["uwb"])


@router.post("/uwb/distances")
async def upload_distances(payload: UwbDistancesIn, db: Session = Depends(get_db)):
    worker = db.get(WorkerState, payload.worker_id)
    if not worker:
        raise HTTPException(404, "작업자를 찾을 수 없습니다.")
    refresh_presence(db)
    measured_ids = {item.anchor_id for item in payload.measurements}
    measured_anchors = db.query(Anchor).filter(Anchor.anchor_id.in_(measured_ids)).all()
    seen_at = utcnow()
    for anchor in measured_anchors:
        anchor.online = True
        anchor.last_seen = seen_at
    anchors = [{"anchor_id": item.anchor_id, "x": item.x, "y": item.y} for item in measured_anchors]
    measurements = measurements_to_dict(payload.measurements, apply_calibration=not payload.distances_calibrated)
    try:
        raw_x, raw_y, confidence = solve_position(anchors, measurements)
    except ValueError as exc:
        create_event(db, "LOCATION_FAILED", str(exc), "warning", payload.worker_id, payload.device_id)
        db.commit()
        raise HTTPException(422, str(exc)) from exc
    x, y = filter_location(payload.worker_id, raw_x, raw_y, (worker.x, worker.y))
    layout = db.get(SiteLayout, settings.site_id)
    worker.x, worker.y = clamp_position(x, y, layout.width if layout else None, layout.height if layout else None)
    worker.confidence = confidence
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
    device = db.get(Device, payload.device_id)
    if not device:
        device = Device(
            device_id=payload.device_id,
            device_type="position_device",
            organization_id=payload.organization_id,
            site_id=payload.site_id,
            worker_id=payload.worker_id,
            helmet_id=payload.helmet_id,
        )
        db.add(device)
    mark_device_seen(device, "uwb")
    recalculate_risk(db, worker)
    db.commit()
    incident = current_incident(db)
    route = calculate_route(db, worker, incident) if incident else None
    result = {"location": {"x": worker.x, "y": worker.y, "confidence": confidence, "raw_x": raw_x, "raw_y": raw_y}, "worker": worker_to_dict(worker), "event": event_to_dict(zone_event) if zone_event else None, "evacuation_route": route}
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




