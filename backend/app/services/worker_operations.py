from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from ..models.entities import WorkerActivity, WorkerAssignment, WorkerQualification

KST = timezone(timedelta(hours=9))
ROLE_NAMES = {"general_worker": "일반작업자", "manager": "관리자", "hot_work_authorized": "화기인가자", "heavy_equipment_operator": "중장비운전자", "unauthorized": "비인가자"}


def activities(db, worker):
    return db.query(WorkerActivity).filter_by(site_id=worker.site_id, worker_id=worker.worker_id).order_by(WorkerActivity.created_at, WorkerActivity.activity_id).all()


def aware(moment):
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment


def activity_spans(rows, now=None):
    """Return state and all accumulated work and break intervals."""
    now = now or datetime.now(timezone.utc)
    state = "off"
    work_start = None
    break_start = None
    work_spans = []
    break_spans = []
    for row in rows:
        moment = aware(row.created_at)
        if row.kind == "start" and state == "off":
            state, work_start = "working", moment
        elif row.kind == "break_start" and state == "working":
            work_spans.append((work_start, moment))
            state, work_start, break_start = "break", None, moment
        elif row.kind == "break_end" and state == "break":
            break_spans.append((break_start, moment))
            state, break_start, work_start = "working", None, moment
        elif row.kind == "end" and state == "working":
            work_spans.append((work_start, moment))
            state, work_start = "off", None
        elif row.kind == "end" and state == "break":
            break_spans.append((break_start, moment))
            state, break_start = "off", None
    if state == "working" and work_start:
        work_spans.append((work_start, now))
    elif state == "break" and break_start:
        break_spans.append((break_start, now))
    return state, work_spans, break_spans


def intervals(rows, now=None):
    """Backward-compatible helper returning work intervals only."""
    state, work_spans, _ = activity_spans(rows, now)
    return state, work_spans


def day_seconds(spans, day):
    beginning = datetime.combine(day, time.min, KST)
    end = beginning + timedelta(days=1)
    return int(sum(max(0, (min(finish, end) - max(start, beginning)).total_seconds()) for start, finish in spans))


def work_summary(db: Session, worker):
    now = datetime.now(timezone.utc)
    rows = activities(db, worker)
    state, spans, break_spans = activity_spans(rows, now)
    return {"state": state, "today_seconds": day_seconds(spans, now.astimezone(KST).date()),
            "today_break_seconds": day_seconds(break_spans, now.astimezone(KST).date()), "server_now": now.isoformat(),
            "history": [{"kind": r.kind, "created_at": aware(r.created_at).isoformat()} for r in rows[-30:]]}


def assignment(db, worker):
    row = db.get(WorkerAssignment, worker.worker_id)
    return {"organization": row.organization if row and row.site_id == worker.site_id else "미등록",
            "team": row.team if row and row.site_id == worker.site_id else "현장팀",
            "job_title": row.job_title if row and row.site_id == worker.site_id else ROLE_NAMES.get(worker.worker_role, worker.worker_role)}


def qualifications(db, worker):
    today = datetime.now(KST).date().isoformat()
    rows = db.query(WorkerQualification).filter_by(site_id=worker.site_id, worker_id=worker.worker_id).order_by(WorkerQualification.name).all()
    result = [{"qualification_id": r.qualification_id, "kind": r.kind, "name": r.name, "required": r.required, "completed": r.completed,
               "expires_on": r.expires_on, "valid": r.completed and (not r.expires_on or r.expires_on >= today)} for r in rows]
    reasons = [r["name"] + (" 미이수/미승인" if not r["completed"] else " 유효기간 만료") for r in result if r["required"] and not r["valid"]]
    if worker.worker_role == "unauthorized":
        reasons.append("작업자 역할이 비인가자로 지정되어 있습니다.")
    return {"items": result, "can_work": not reasons, "reasons": reasons}
