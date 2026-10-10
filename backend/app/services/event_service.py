import json
from uuid import uuid4

from sqlalchemy.orm import Session

from ..models.entities import Device, Event, WorkerState


def create_event(
    db: Session,
    event_type: str,
    message: str,
    severity: str = "info",
    worker_id: str | None = None,
    device_id: str | None = None,
    details: dict | None = None,
    site_id: str | None = None,
) -> Event:
    resolved_site_id = site_id
    if not resolved_site_id and worker_id:
        worker = db.get(WorkerState, worker_id)
        resolved_site_id = worker.site_id if worker else None
    if not resolved_site_id and device_id:
        device = db.get(Device, device_id)
        resolved_site_id = device.site_id if device else None
    event = Event(
        event_id=str(uuid4()),
        event_type=event_type,
        severity=severity,
        message=message,
        worker_id=worker_id,
        device_id=device_id,
        site_id=resolved_site_id or "site-001",
        details_json=json.dumps(details or {}, ensure_ascii=False),
    )
    db.add(event)
    db.flush()
    return event


def event_to_dict(event: Event) -> dict:
    return {
        "event_id": event.event_id,
        "site_id": event.site_id,
        "event_type": event.event_type,
        "severity": event.severity,
        "message": event.message,
        "worker_id": event.worker_id,
        "device_id": event.device_id,
        "details": json.loads(event.details_json or "{}"),
        "status": event.status,
        "created_at": event.created_at.isoformat() + "Z",
    }
