import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models.entities import Anchor, Device, Event, Obstacle, SiteLayout, WorkerState, Zone
from ..services.event_service import event_to_dict
from ..services.serializers import device_to_dict, worker_to_dict
from ..services.presence_service import refresh_presence
from ..services.evacuation_service import evacuation_snapshot

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/snapshot")
def snapshot(db: Session = Depends(get_db)):
    refresh_presence(db)
    anchors = db.query(Anchor).order_by(Anchor.anchor_id).all()
    workers = db.query(WorkerState).all()
    layout = db.get(SiteLayout, settings.site_id)
    zones = db.query(Zone).all()
    recent_events = db.query(Event).order_by(Event.created_at.desc()).limit(50).all()
    unresolved_events = db.query(Event).filter(Event.status != "resolved").order_by(Event.created_at.desc()).all()
    events_by_id = {row.event_id: row for row in [*unresolved_events, *recent_events]}
    events = sorted(events_by_id.values(), key=lambda row: row.created_at, reverse=True)
    return {
        "mode": settings.operation_mode,
        "site": {
            "site_id": settings.site_id,
            "map_id": "map-001",
            "name": layout.name if layout else settings.site_name,
            "width": layout.width if layout else settings.site_width_m,
            "height": layout.height if layout else settings.site_height_m,
        },
        "workers": [worker_to_dict(row) for row in workers],
        "devices": [device_to_dict(row) for row in db.query(Device).all()],
        "anchors": [{"anchor_id": a.anchor_id, "name": a.name, "x": a.x, "y": a.y, "z": a.z, "online": a.online, "last_seen": a.last_seen.isoformat() + "Z"} for a in anchors],
        "obstacles": [{"obstacle_id": o.obstacle_id, "name": o.name, "x": o.x, "y": o.y, "width": o.width, "height": o.height} for o in db.query(Obstacle).filter(Obstacle.site_id == settings.site_id).all()],
        "zones": [
            {
                "zone_id": z.zone_id,
                "zone_name": z.zone_name,
                "zone_type": z.zone_type,
                "zone_category": z.zone_category,
                "coordinates": json.loads(z.coordinates_json),
                "required_ppe": json.loads(z.required_ppe_json),
                "allowed_worker_ids": json.loads(z.allowed_worker_ids_json),
                "risk_weight": z.risk_weight,
                "warning_message": z.warning_message,
                "active": z.active,
            }
            for z in zones
        ],
        "events": [event_to_dict(row) for row in events],
        "evacuation": evacuation_snapshot(db),
    }




