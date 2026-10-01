from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.entities import WorkerState
from ..services.risk_service import recalculate_risk
from ..services.serializers import worker_to_dict

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("/{worker_id}")
def get_risk(worker_id: str, db: Session = Depends(get_db)):
    worker = db.get(WorkerState, worker_id)
    if not worker:
        raise HTTPException(404, "작업자를 찾을 수 없습니다.")
    recalculate_risk(db, worker)
    db.commit()
    return worker_to_dict(worker)

