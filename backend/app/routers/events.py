import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.entities import Event, WorkerState
from ..services.event_service import event_to_dict
from ..services.risk_service import recalculate_risk
from ..websocket import manager

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
def list_events(limit: int = 100, status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Event)
    if status:
        query = query.filter(Event.status == status)
    rows = query.order_by(Event.created_at.desc()).limit(min(limit, 500)).all()
    return [event_to_dict(row) for row in rows]


def _life_safety_intent(row: Event) -> str | None:
    try:
        intent = json.loads(row.details_json or "{}").get("intent")
    except (json.JSONDecodeError, TypeError):
        return None
    return intent if intent in {"help", "emergency"} else None


async def change_status(event_id: str, status: str, db: Session) -> dict:
    row = db.get(Event, event_id)
    if not row:
        raise HTTPException(404, "이벤트를 찾을 수 없습니다.")
    row.status = status
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
    result = event_to_dict(row)
    await manager.broadcast("event_status", result)
    return result


@router.post("/{event_id}/acknowledge")
async def acknowledge(event_id: str, db: Session = Depends(get_db)):
    return await change_status(event_id, "acknowledged", db)


@router.post("/{event_id}/resolve")
async def resolve(event_id: str, db: Session = Depends(get_db)):
    return await change_status(event_id, "resolved", db)

