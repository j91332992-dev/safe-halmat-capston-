from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.entities import Event
from ..services.event_service import event_to_dict
from ..websocket import manager

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
def list_events(limit: int = 100, status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Event)
    if status:
        query = query.filter(Event.status == status)
    rows = query.order_by(Event.created_at.desc()).limit(min(limit, 500)).all()
    return [event_to_dict(row) for row in rows]


async def change_status(event_id: str, status: str, db: Session) -> dict:
    row = db.get(Event, event_id)
    if not row:
        raise HTTPException(404, "이벤트를 찾을 수 없습니다.")
    row.status = status
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

