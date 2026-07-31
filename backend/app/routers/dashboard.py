import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models.entities import Anchor, Device, Event, WorkerState, Zone
from ..services.event_service import event_to_dict
from ..services.serializers import device_to_dict, worker_to_dict

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/snapshot")
def snapshot(db: Session = Depends(get_db)):
    anchors = db.query(Anchor).order_by(Anchor.anchor_id).all()
    zones = db.query(Zone).all()
    events = db.query(Event).order_by(Event.created_at.desc()).limit(50).all()
    return {
        "mode": settings.operation_mode,
        "site": {"site_id": "site-001", "map_id": "map-001", "name": "한미르 실증 현장", "width": 12, "height": 8},
        "workers": [worker_to_dict(row) for row in db.query(WorkerState).all()],
        "devices": [device_to_dict(row) for row in db.query(Device).all()],
        "anchors": [{"anchor_id": a.anchor_id, "name": a.name, "x": a.x, "y": a.y, "z": a.z, "online": a.online} for a in anchors],
        "zones": [
            {
                "zone_id": z.zone_id,
                "zone_name": z.zone_name,
                "zone_type": z.zone_type,
                "coordinates": json.loads(z.coordinates_json),
                "required_ppe": json.loads(z.required_ppe_json),
                "risk_weight": z.risk_weight,
                "warning_message": z.warning_message,
                "active": z.active,
            }
            for z in zones
        ],
        "events": [event_to_dict(row) for row in events],
    }

