from datetime import timedelta

from sqlalchemy.orm import Session

from ..config import settings
from ..database import utcnow
from ..models.entities import Anchor, Device


def refresh_presence(db: Session) -> tuple[list[Device], list[Anchor]]:
    cutoff = utcnow() - timedelta(seconds=settings.device_offline_seconds)
    devices = db.query(Device).all()
    anchors = db.query(Anchor).all()
    for device in devices:
        device.online = bool(device.online and device.last_seen >= cutoff)
    for anchor in anchors:
        anchor.online = bool(anchor.online and anchor.last_seen >= cutoff)
    db.flush()
    return devices, anchors
