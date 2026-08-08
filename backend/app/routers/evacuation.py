import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models.entities import EvacuationIncident, SiteLayout, WorkerState
from ..schemas.api import FireCancelIn, FireTriggerIn, FireZoneIn
from ..services.evacuation_service import (
    calculate_route,
    cancel_incident,
    current_incident,
    evacuation_snapshot,
    incident_to_dict,
    set_fire_zone,
    trigger_fire,
)
from ..services.event_service import create_event, event_to_dict
from ..services.evacuation_guidance_service import assistant_device_id, clear_guidance, send_helmet_guidance
from ..services.risk_service import recalculate_risk
from ..websocket import manager

router = APIRouter(prefix="/api/evacuation", tags=["evacuation"])


async def _send_all_guidance(db: Session, snapshot: dict, force: bool) -> list[dict]:
    incident = snapshot.get("incident")
    if not incident:
        return []
    deliveries = []
    for worker_id, route in snapshot.get("routes", {}).items():
        deliveries.append(
            await send_helmet_guidance(
                worker_id,
                assistant_device_id(db, worker_id),
                incident["incident_id"],
                route,
                force=force,
            )
        )
    return deliveries


@router.get("/current")
def get_current(worker_id: str | None = None, db: Session = Depends(get_db)):
    result = evacuation_snapshot(db)
    if worker_id and result["incident"]:
        worker = db.get(WorkerState, worker_id)
        if not worker:
            raise HTTPException(404, "작업자를 찾을 수 없습니다.")
        result["route"] = calculate_route(db, worker, current_incident(db))
    return result


@router.post("/trigger")
async def trigger(payload: FireTriggerIn, db: Session = Depends(get_db)):
    worker = db.get(WorkerState, payload.worker_id)
    if not worker:
        raise HTTPException(404, "작업자를 찾을 수 없습니다.")
    incident, created = trigger_fire(db, payload.source, payload.worker_id, payload.details)
    event = None
    if created:
        event = create_event(
            db,
            "FIRE_EVACUATION_TRIGGERED",
            "화재가 감지되었습니다. 발생 위치 확인 중 안내와 가장 가까운 비상구 거리 안내를 시작합니다.",
            "emergency",
            payload.worker_id,
            details={"incident_id": incident.incident_id, "source": payload.source},
        )
    db.commit()
    result = {**evacuation_snapshot(db), "event": event_to_dict(event) if event else None}
    result["helmet_guidance"] = await _send_all_guidance(db, result, force=created)
    await manager.broadcast("evacuation_triggered", result)
    return result


@router.post("/{incident_id}/confirm-zone")
async def confirm_zone(incident_id: str, payload: FireZoneIn, db: Session = Depends(get_db)):
    incident = db.get(EvacuationIncident, incident_id)
    if not incident or incident.status not in ("pending_manager", "active"):
        raise HTTPException(404, "확인 가능한 화재 사건이 없습니다.")
    layout = db.get(SiteLayout, settings.site_id)
    width = layout.width if layout else settings.site_width_m
    height = layout.height if layout else settings.site_height_m
    zone = payload.model_dump()
    zone["width"] = min(zone["width"], width)
    zone["height"] = min(zone["height"], height)
    zone["x"] = min(zone["x"], max(0.0, width - zone["width"]))
    zone["y"] = min(zone["y"], max(0.0, height - zone["height"]))
    set_fire_zone(incident, zone)
    event = create_event(
        db,
        "FIRE_ZONE_CONFIRMED",
        "관리자가 화재 발생 위치를 확정했습니다. 작업자에게 화재 위치와 비상구 거리를 다시 안내합니다.",
        "emergency",
        incident.worker_id,
        details={"incident_id": incident.incident_id, "fire_zone": zone},
    )
    db.commit()
    result = {**evacuation_snapshot(db), "event": event_to_dict(event)}
    result["helmet_guidance"] = await _send_all_guidance(db, result, force=True)
    await manager.broadcast("fire_zone_confirmed", result)
    return result


@router.post("/{incident_id}/cancel")
async def cancel(incident_id: str, payload: FireCancelIn, db: Session = Depends(get_db)):
    incident = db.get(EvacuationIncident, incident_id)
    if not incident or incident.status not in ("pending_manager", "active"):
        raise HTTPException(404, "취소 가능한 화재 사건이 없습니다.")
    cancel_incident(incident, payload.reason)
    clear_guidance()
    for worker in db.query(WorkerState).all():
        hazards = json.loads(worker.hazard_json or "{}")
        for key in ("fire", "large_fire", "fire_reported"):
            hazards[key] = False
        worker.hazard_json = json.dumps(hazards, ensure_ascii=False)
        recalculate_risk(db, worker)
    labels = {"false_alarm": "오판단", "no_fire": "화재 없음", "resolved": "화재 종료"}
    event = create_event(
        db,
        "FIRE_EVACUATION_CANCELLED" if payload.reason != "resolved" else "FIRE_RESOLVED",
        f"관리자가 {labels[payload.reason]}으로 처리하여 화재 알림을 종료했습니다.",
        "warning" if payload.reason != "resolved" else "info",
        incident.worker_id,
        details={"incident_id": incident.incident_id, "reason": payload.reason},
    )
    db.commit()
    result = {"incident": incident_to_dict(incident), "routes": {}, "event": event_to_dict(event)}
    await manager.broadcast("evacuation_cancelled", result)
    return result

