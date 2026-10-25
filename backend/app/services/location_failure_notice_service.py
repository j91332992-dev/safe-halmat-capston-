"""Rate-limit user-facing failures; raw UWB observations remain per-cycle."""
import time

from ..config import settings
from ..database import utcnow
from ..models.entities import Event
from .event_service import create_event

_last_notices: dict[tuple[str, str], float] = {}


def create_location_failure_notice(db, message, worker_id, device_id, site_id):
    # One notice per worker/site, even when failure reasons alternate.
    key = (site_id, worker_id)
    now = time.monotonic()
    interval = settings.uwb_location_failure_notice_seconds
    previous = _last_notices.get(key)
    if previous is not None and now - previous < interval:
        return None
    # Check persisted events only on the first cycle / at the interval boundary.
    # A server restart must not immediately repeat the same warning.
    last = (db.query(Event.created_at)
            .filter(Event.site_id == site_id, Event.worker_id == worker_id,
                    Event.event_type == "LOCATION_FAILED")
            .order_by(Event.created_at.desc()).first())
    age = max(0.0, (utcnow() - last[0]).total_seconds()) if last else interval
    if age < interval:
        stamp = now - age
        event = None
    else:
        event = create_event(db, "LOCATION_FAILED", message, "warning", worker_id,
                             device_id, site_id=site_id,
                             details={"notice_interval_seconds": interval})
        stamp = now
    if key not in _last_notices and len(_last_notices) >= 1000:
        _last_notices.pop(min(_last_notices, key=_last_notices.get))
    _last_notices[key] = stamp
    return event
