from fastapi import APIRouter, Depends, HTTPException, Header
from datetime import date
from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.entities import WorkerState, WorkerAssignment, WorkerQualification
from ..schemas.api import WorkerUpdateIn
from ..services.serializers import worker_to_dict
from .auth import require_site, session_identity
from ..services.worker_operations import assignment, qualifications, work_summary
from .worker_app import MessageRequest, messages, send_message

router = APIRouter(prefix="/api/workers", tags=["workers"])


@router.put("/{worker_id}")
def update_worker(worker_id: str, payload: WorkerUpdateIn, site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    worker = db.get(WorkerState, worker_id)
    if not worker or worker.site_id != site_id:
        raise HTTPException(404, "작업자를 찾을 수 없습니다.")
    worker.worker_name = payload.worker_name.strip()
    worker.worker_role = payload.worker_role
    worker.notes = payload.notes.strip()
    db.commit()
    return worker_to_dict(worker)


class QualificationIn(BaseModel):
    kind: Literal["education", "permit"]
    name: str = Field(min_length=1, max_length=100)
    required: bool = True
    completed: bool = False
    expires_on: date | None = None


class OperationsIn(BaseModel):
    organization: str = Field(default="", max_length=100)
    team: str = Field(default="현장팀", min_length=1, max_length=80)
    job_title: str = Field(default="일반작업자", min_length=1, max_length=80)
    qualifications: list[QualificationIn] = Field(default_factory=list, max_length=50)


def scoped_worker(worker_id, site_id, db):
    row = db.get(WorkerState, worker_id)
    if not row or row.site_id != site_id:
        raise HTTPException(404, "작업자를 찾을 수 없습니다.")
    return row


@router.get("/{worker_id}/operations")
def operations(worker_id: str, site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    worker = scoped_worker(worker_id, site_id, db)
    return {**assignment(db, worker), "eligibility": qualifications(db, worker), "work": work_summary(db, worker)}


@router.put("/{worker_id}/operations")
def save_operations(worker_id: str, payload: OperationsIn, site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    scoped_worker(worker_id, site_id, db)
    if not payload.team.strip() or not payload.job_title.strip() or any(not q.name.strip() for q in payload.qualifications):
        raise HTTPException(400, "팀·직책·교육/허가 이름을 입력하세요.")
    row = db.get(WorkerAssignment, worker_id)
    if not row:
        row = WorkerAssignment(worker_id=worker_id, site_id=site_id)
        db.add(row)
    row.site_id, row.organization, row.team, row.job_title = site_id, payload.organization.strip(), payload.team.strip(), payload.job_title.strip()
    db.query(WorkerQualification).filter_by(site_id=site_id, worker_id=worker_id).delete()
    for q in payload.qualifications:
        db.add(WorkerQualification(qualification_id=str(uuid4()), site_id=site_id, worker_id=worker_id, kind=q.kind,
                                  name=q.name.strip(), required=q.required, completed=q.completed,
                                  expires_on=q.expires_on.isoformat() if q.expires_on else None))
    db.commit()
    return operations(worker_id, site_id, db)


@router.get("/{worker_id}/chat")
def admin_chat(worker_id: str, before: int | None = None, site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    worker = scoped_worker(worker_id, site_id, db)
    team = assignment(db, worker)["team"]
    return {"team": team, "messages": messages(db, site_id, team, before)}


@router.post("/{worker_id}/chat")
def admin_chat_send(worker_id: str, payload: MessageRequest, authorization: str | None = Header(default=None), site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    worker = scoped_worker(worker_id, site_id, db)
    identity = session_identity(authorization)
    return send_message(db, site_id, assignment(db, worker)["team"], str(identity["username"]), "관리자 " + str(identity["username"]), payload.content)
