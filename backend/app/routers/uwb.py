import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db, utcnow
from ..models.entities import Anchor, Device, Location, WorkerState, Zone
from ..schemas.api import UwbDistancesIn
from ..services.event_service import create_event, event_to_dict
from ..services.location_filter_service import filter_location
from ..services.location_service import solve_position
from ..services.risk_service import recalculate_risk
from ..services.serializers import worker_to_dict
from ..services.uwb_service import measurements_to_dict
from ..services.zone_service import confirm_zone, point_in_zone
from ..websocket import manager

router = APIRouter(prefix="/api", tags=["uwb"])


@router.post("/uwb/distances")
async def upload_distances(payload: UwbDistancesIn, db: Session = Depends(get_db)):
    worker = db.get(WorkerState, payload.worker_id)
    if not worker:
        raise HTTPException(404, "작업자를 찾을 수 없습니다.")
    anchors = [
        {"anchor_id": a.anchor_id, "x": a.x, "y": a.y}
        for a in db.query(Anchor).filter(Anchor.online.is_(True)).all()
    ]
    measurements = measurements_to_dict(payload.measurements)
    try:
        raw_x, raw_y, confidence = solve_position(anchors, measurements)
    except ValueError as exc:
        create_event(db, "LOCATION_FAILED", str(exc), "warning", payload.worker_id, payload.device_id)
        db.commit()
        raise HTTPException(422, str(exc)) from exc
    x, y = filter_location(payload.worker_id, raw_x, raw_y, (worker.x, worker.y))
    worker.x, worker.y, worker.confidence = max(0, min(12, x)), max(0, min(8, y)), confidence
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
    if device:
        device.last_uwb_at = utcnow()
    recalculate_risk(db, worker)
    db.commit()
    result = {"location": {"x": worker.x, "y": worker.y, "confidence": confidence, "raw_x": raw_x, "raw_y": raw_y}, "worker": worker_to_dict(worker), "event": event_to_dict(zone_event) if zone_event else None}
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
    rows = db.query(Location).filter(Location.worker_id == worker_id).order_by(Location.created_at.desc()).limit(min(limit, 500)).all()
    return [
        {"x": r.x, "y": r.y, "confidence": r.confidence, "created_at": r.created_at.isoformat() + "Z"}
        for r in reversed(rows)
    ]

