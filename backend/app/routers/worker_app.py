from datetime import date, datetime, timedelta, timezone
import calendar
import json
from pydantic import BaseModel, Field
from sqlalchemy import update
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.entities import Device, Event, SiteLayout, WorkerActivity, WorkerState, TeamMessage
from ..services.event_service import event_to_dict
from ..services.risk_service import recalculate_risk
from ..services.serializers import worker_to_dict
from ..websocket import manager, call_manager
from .auth import require_worker
from ..services.worker_operations import activities, activity_spans, assignment, aware, day_seconds, KST, qualifications, work_summary
from .layout import applied_design

router = APIRouter(prefix="/api/worker-app", tags=["worker-app"])


def _worker(db: Session, identity: dict[str, object]) -> WorkerState:
    worker = db.get(WorkerState, identity["worker_id"])
    if not worker or worker.site_id != identity["site_id"]:
        raise HTTPException(403, "작업자 배정을 확인할 수 없습니다.")
    return worker


@router.get("/me")
def me(identity: dict[str, object] = Depends(require_worker), db: Session = Depends(get_db)):
    worker = _worker(db, identity)
    layout = db.get(SiteLayout, worker.site_id)
    devices = db.query(Device).filter(Device.site_id == worker.site_id, Device.worker_id == worker.worker_id).all()
    events = db.query(Event).filter(Event.site_id == worker.site_id, Event.worker_id == worker.worker_id).order_by(Event.created_at.desc()).limit(20).all()
    work = work_summary(db, worker)
    return {
        "worker": {"worker_id": worker.worker_id, "worker_name": worker.worker_name, "site_name": layout.name if layout else worker.site_id, **assignment(db, worker),
                   "current_zone": worker.current_zone, "x": worker.x, "y": worker.y, "confidence": worker.confidence,
                   "risk_level": worker.risk_level, "emergency": worker.emergency, "updated_at": worker.updated_at.isoformat() + "Z"},
        "devices": [{"device_id": d.device_id, "device_type": d.device_type, "online": d.online, "battery": d.battery,
                     "last_seen": d.last_seen.isoformat() + "Z", "last_uwb_at": d.last_uwb_at.isoformat() + "Z" if d.last_uwb_at else None} for d in devices],
        "events": [event_to_dict(e) for e in events],
        "work": work, "eligibility": qualifications(db, worker),
    }


class WorkRequest(BaseModel):
    helmet: bool = False
    vest: bool = False
    glove: bool = False


@router.post("/work/{kind}")
async def record_work(kind: str, payload: WorkRequest | None = None, identity: dict[str, object] = Depends(require_worker), db: Session = Depends(get_db)):
    worker = _worker(db, identity)
    # Serialize state transitions before reading the activity history (SQLite).
    db.execute(update(WorkerState).where(WorkerState.worker_id == worker.worker_id).values(updated_at=WorkerState.updated_at))
    state = work_summary(db, worker)["state"]
    allowed = {"off": "start", "working": "break_start", "break": "break_end"}
    if kind != allowed.get(state) and not (kind == "end" and state in {"working", "break"}):
        raise HTTPException(409, "현재 작업 상태에서 실행할 수 없습니다.")
    if kind in {"start", "break_end"}:
        eligible = qualifications(db, worker)
        if not eligible["can_work"]:
            raise HTTPException(409, "작업 조건을 확인하세요: " + ", ".join(eligible["reasons"]))
    if kind == "start":
        if not payload or not (payload.helmet and payload.vest and payload.glove):
            raise HTTPException(400, "안전모·작업 조끼·장갑 착용을 모두 확인하세요.")
        db.add(Event(event_id=str(uuid4()), site_id=worker.site_id, worker_id=worker.worker_id,
                     event_type="SAFETY_CHECKLIST", message="작업 시작 전 안전모·조끼·장갑 착용 확인", severity="info",
                     status="resolved", details_json=json.dumps(payload.model_dump())))
    db.add(WorkerActivity(activity_id=str(uuid4()), worker_id=worker.worker_id, site_id=worker.site_id, kind=kind))
    db.commit()
    work = work_summary(db, worker)
    await manager.broadcast("work_status", {"worker_id": worker.worker_id, "work": work}, site_id=worker.site_id)
    return {"ok": True, "work": work}


@router.get("/calendar")
def work_calendar(month: str, identity: dict[str, object] = Depends(require_worker), db: Session = Depends(get_db)):
    worker = _worker(db, identity)
    try:
        first = date.fromisoformat(month + "-01")
    except ValueError:
        raise HTTPException(400, "월은 YYYY-MM 형식으로 입력하세요.")
    if not 1900 <= first.year <= 2100:
        raise HTTPException(400, "조회 가능한 연도는 1900~2100입니다.")
    rows = activities(db, worker)
    _, spans, break_spans = activity_spans(rows)
    days = []
    for offset in range(calendar.monthrange(first.year, first.month)[1]):
        day = first + timedelta(days=offset)
        beginning = datetime.combine(day, datetime.min.time(), KST)
        end = beginning + timedelta(days=1)
        days.append({"date": day.isoformat(), "seconds": day_seconds(spans, day), "break_seconds": day_seconds(break_spans, day),
                     "records": [{"kind": r.kind, "created_at": aware(r.created_at).isoformat()} for r in rows if aware(r.created_at).astimezone(KST).date() == day],
                     "intervals": [{"start": max(start, beginning).isoformat(), "end": min(finish, end).isoformat()} for start, finish in spans if start < end and finish > beginning],
                     "break_intervals": [{"start": max(start, beginning).isoformat(), "end": min(finish, end).isoformat()} for start, finish in break_spans if start < end and finish > beginning]})
    return {"month": month, "timezone": "Asia/Seoul", "days": days}


@router.get("/map")
def worker_map(identity: dict[str, object] = Depends(require_worker), db: Session = Depends(get_db)):
    worker = _worker(db, identity)
    design = applied_design(db, worker.site_id)
    # Do not expose other workers or restricted-zone membership lists.
    for zone in design["zones"]:
        zone.pop("allowed_worker_ids", None)
    db.commit()
    return design


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


def messages(db, site_id, team, before=None):
    query = db.query(TeamMessage).filter_by(site_id=site_id, team=team)
    if before:
        query = query.filter(TeamMessage.message_id < before)
    rows = query.order_by(TeamMessage.message_id.desc()).limit(100).all()
    return [{"message_id": r.message_id, "sender_id": r.sender_id, "sender_name": r.sender_name, "content": r.content, "created_at": aware(r.created_at).isoformat()} for r in reversed(rows)]


def send_message(db, site_id, team, sender_id, sender_name, content):
    content = content.strip()
    if not content:
        raise HTTPException(400, "메시지를 입력하세요.")
    row = TeamMessage(site_id=site_id, team=team, sender_id=sender_id, sender_name=sender_name, content=content)
    db.add(row)
    db.commit()
    return {"ok": True, "message_id": row.message_id}


@router.get("/chat")
def worker_chat(before: int | None = None, identity: dict[str, object] = Depends(require_worker), db: Session = Depends(get_db)):
    worker = _worker(db, identity)
    team = assignment(db, worker)["team"]
    return {"team": team, "messages": messages(db, worker.site_id, team, before)}


@router.post("/chat")
def worker_chat_send(payload: MessageRequest, identity: dict[str, object] = Depends(require_worker), db: Session = Depends(get_db)):
    worker = _worker(db, identity)
    return send_message(db, worker.site_id, assignment(db, worker)["team"], worker.worker_id, worker.worker_name, payload.content)


@router.post("/sos")
async def sos(identity: dict[str, object] = Depends(require_worker), db: Session = Depends(get_db)):
    worker = _worker(db, identity)
    existing = db.query(Event).filter_by(worker_id=worker.worker_id, site_id=worker.site_id, event_type="WORKER_SOS").filter(Event.status != "resolved").first()
    if existing:
        return event_to_dict(existing)
    device = db.query(Device).filter_by(site_id=worker.site_id, worker_id=worker.worker_id, device_type="assistant_device").first()
    event = Event(event_id=str(uuid4()), event_type="WORKER_SOS", site_id=worker.site_id, severity="emergency",
                  message=f"{worker.worker_name} 작업자 SOS 요청", worker_id=worker.worker_id, device_id=device.device_id if device else None, status="open",
                  details_json=json.dumps({"intent": "emergency", "source": "worker_app"}))
    db.add(event)
    worker.emergency = True
    recalculate_risk(db, worker)
    db.commit()
    db.refresh(event)
    await manager.broadcast("worker_updated", {"worker": worker_to_dict(worker), "event": event_to_dict(event)}, site_id=worker.site_id)
    return event_to_dict(event)


@router.post("/call-manager")
async def request_manager_call(identity: dict[str, object] = Depends(require_worker), db: Session = Depends(get_db)):
    worker = _worker(db, identity)
    device = db.query(Device).filter_by(site_id=worker.site_id, worker_id=worker.worker_id, device_type="assistant_device").first()
    if not device or not call_manager.device_online(device.device_id):
        raise HTTPException(409, "안전모 통화 연결이 오프라인입니다. SOS 요청 또는 현장 비상 연락망을 이용하세요.")
    existing = db.query(Event).filter_by(site_id=worker.site_id, worker_id=worker.worker_id, event_type="VOICE_COMMAND", status="open").all()
    for row in existing:
        if json.loads(row.details_json or "{}").get("intent") == "call_manager":
            return event_to_dict(row)
    event = Event(event_id=str(uuid4()), site_id=worker.site_id, worker_id=worker.worker_id, device_id=device.device_id,
                  event_type="VOICE_COMMAND", severity="warning", status="open", message=f"{worker.worker_name} 관리자 통화 요청",
                  details_json=json.dumps({"intent": "call_manager", "source": "worker_app"}))
    db.add(event)
    db.commit()
    db.refresh(event)
    await manager.broadcast("worker_updated", {"worker": worker_to_dict(worker), "event": event_to_dict(event)}, site_id=worker.site_id)
    await call_manager.begin_call_request(device.device_id, worker.worker_id, event.event_id)
    return event_to_dict(event)
