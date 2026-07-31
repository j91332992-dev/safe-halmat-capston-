import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models.entities import Device, WorkerState
from ..schemas.api import MockScenarioIn, SystemModeIn
from ..services.event_service import create_event, event_to_dict
from ..services.risk_service import recalculate_risk
from ..services.serializers import worker_to_dict
from ..websocket import manager

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/mode")
def get_mode():
    return {"mode": settings.operation_mode}


@router.post("/mode")
async def set_mode(payload: SystemModeIn):
    settings.operation_mode = payload.mode
    await manager.broadcast("mode_changed", {"mode": payload.mode})
    return {"mode": payload.mode, "message": f"{payload.mode} 모드로 전환했습니다."}


@router.post("/mock/scenario")
async def scenario(payload: MockScenarioIn, db: Session = Depends(get_db)):
    if settings.operation_mode != "mock":
        raise HTTPException(409, "mock 모드에서만 시나리오를 실행할 수 있습니다.")
    worker = db.get(WorkerState, payload.worker_id)
    if not worker:
        raise HTTPException(404, "작업자를 찾을 수 없습니다.")
    worker.emergency = payload.scenario == "emergency"
    worker.ppe_json = json.dumps({"vest": payload.scenario != "ppe_missing", "glove": payload.scenario != "ppe_missing"})
    worker.hazard_json = json.dumps({"fire": payload.scenario == "fire", "smoke": payload.scenario == "smoke"})
    if payload.scenario == "danger_zone":
        worker.x, worker.y, worker.current_zone = 8.5, 3.5, "zone-hot-work"
    elif payload.scenario == "normal":
        worker.x, worker.y, worker.current_zone = 2.0, 2.0, None
    devices = db.query(Device).filter(Device.worker_id == payload.worker_id).all()
    for device in devices:
        device.online = payload.scenario != "device_offline"
    recalculate_risk(db, worker)
    event = create_event(
        db,
        f"MOCK_{payload.scenario.upper()}",
        f"더미 시나리오 실행: {payload.scenario}",
        "emergency" if payload.scenario == "emergency" else "danger" if payload.scenario in ("fire", "smoke", "danger_zone") else "info",
        payload.worker_id,
        details={"scenario": payload.scenario},
    )
    db.commit()
    result = {"worker": worker_to_dict(worker), "event": event_to_dict(event)}
    await manager.broadcast("mock_scenario", result)
    return result

