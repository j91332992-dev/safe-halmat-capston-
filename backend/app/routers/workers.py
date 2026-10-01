from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.entities import WorkerState
from ..schemas.api import WorkerUpdateIn
from ..services.serializers import worker_to_dict

router = APIRouter(prefix="/api/workers", tags=["workers"])


@router.put("/{worker_id}")
def update_worker(worker_id: str, payload: WorkerUpdateIn, db: Session = Depends(get_db)):
    worker = db.get(WorkerState, worker_id)
    if not worker:
        raise HTTPException(404, "작업자를 찾을 수 없습니다.")
    worker.worker_name = payload.worker_name.strip()
    worker.worker_role = payload.worker_role
    worker.notes = payload.notes.strip()
    db.commit()
    return worker_to_dict(worker)
