import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.entities import Event, FallIncident, WorkerState
from .auth import require_site
from ..services.event_service import event_to_dict
from ..services.risk_service import recalculate_risk
from ..websocket import call_manager, manager

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
def list_events(limit: int = 100, status: str | None = None, site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    query = db.query(Event).filter(Event.site_id == site_id)
    if status:
        query = query.filter(Event.status == status)
    rows = query.order_by(Event.created_at.desc()).limit(min(limit, 500)).all()
    return [event_to_dict(row) for row in rows]


def _life_safety_intent(row: Event) -> str | None:
    if row.event_type == "WORKER_SOS":
        return "emergency"
    try:
        intent = json.loads(row.details_json or "{}").get("intent")
    except (json.JSONDecodeError, TypeError):
        return None
    return intent if intent in {"help", "emergency"} else None


async def change_status(event_id: str, status: str, site_id: str, db: Session) -> dict:
    row = db.get(Event, event_id)
    if not row or row.site_id != site_id:
        raise HTTPException(404, "이벤트를 찾을 수 없습니다.")
    intent = None
    try:
        intent = json.loads(row.details_json or "{}").get("intent")
    except (json.JSONDecodeError, TypeError):
        pass
    if row.event_type == "FALL_SUSPECTED" and status == "resolved":
        incident = db.get(FallIncident, row.event_id)
        if incident and incident.state in {"waiting_prompt", "waiting_response"}:
            raise HTTPException(409, "착용자 응답 확인 중에는 사건을 종료할 수 없습니다.")
    row.status = status
    if row.event_type == "FALL_SUSPECTED" and status == "resolved":
        db.flush()
        worker = db.get(WorkerState, row.worker_id)
        other_emergencies = db.query(Event).filter(Event.worker_id == row.worker_id,
            Event.event_type == "FALL_SUSPECTED", Event.severity == "emergency", Event.status != "resolved").count()
        if worker and not other_emergencies:
            hazards = json.loads(worker.hazard_json or "{}")
            hazards.pop("fall_emergency", None)
            worker.hazard_json = json.dumps(hazards, ensure_ascii=False)
            recalculate_risk(db, worker)
    if status == "resolved" and row.worker_id and _life_safety_intent(row):
        related = db.query(Event).filter(Event.worker_id == row.worker_id, Event.status != "resolved").all()
        for item in related:
            if _life_safety_intent(item):
                item.status = "resolved"
        worker = db.get(WorkerState, row.worker_id)
        if worker:
            worker.emergency = False
            recalculate_risk(db, worker)
    db.commit()
    if status == "resolved" and intent == "call_manager" and row.device_id:
        await call_manager.cancel_call_request(row.device_id, row.event_id, reason="dismissed")
        db.refresh(row)
    result = event_to_dict(row)
    await manager.broadcast("event_status", result)
    return result


@router.post("/resolve-all")
async def resolve_all(site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    """Mark every unresolved event for the signed-in site as resolved."""
    event_ids = [row.event_id for row in db.query(Event).filter(Event.site_id == site_id, Event.status != "resolved").all()
                 if not (row.event_type == "FALL_SUSPECTED" and
                         json.loads(row.details_json or "{}").get("fall_state") in {"waiting_prompt", "waiting_response"})]
    for event_id in event_ids:
        await change_status(event_id, "resolved", site_id, db)
    return {"resolved_count": len(event_ids)}


@router.post("/{event_id}/acknowledge")
async def acknowledge(event_id: str, site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    return await change_status(event_id, "acknowledged", site_id, db)


@router.post("/{event_id}/resolve")
async def resolve(event_id: str, site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    return await change_status(event_id, "resolved", site_id, db)

