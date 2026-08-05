import json

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.entities import Zone
from ..schemas.api import ZoneIn

router = APIRouter(prefix="/api/zones", tags=["zones"])


def serialize(row: Zone) -> dict:
    return {
        "zone_id": row.zone_id,
        "zone_name": row.zone_name,
        "zone_type": row.zone_type,
        "coordinates": json.loads(row.coordinates_json),
        "required_ppe": json.loads(row.required_ppe_json),
        "allowed_worker_ids": json.loads(row.allowed_worker_ids_json),
        "risk_weight": row.risk_weight,
        "warning_message": row.warning_message,
        "max_stay_seconds": row.max_stay_seconds,
        "active": row.active,
    }


def assign(row: Zone, payload: ZoneIn) -> None:
    row.zone_name = payload.zone_name
    row.zone_type = payload.zone_type
    row.coordinates_json = json.dumps(payload.coordinates)
    row.required_ppe_json = json.dumps(payload.required_ppe)
    row.allowed_worker_ids_json = json.dumps(payload.allowed_worker_ids)
    row.risk_weight = payload.risk_weight
    row.warning_message = payload.warning_message
    row.max_stay_seconds = payload.max_stay_seconds
    row.active = payload.active


@router.get("")
def list_zones(db: Session = Depends(get_db)):
    return [serialize(row) for row in db.query(Zone).all()]


@router.post("")
def create_zone(payload: ZoneIn, db: Session = Depends(get_db)):
    if db.get(Zone, payload.zone_id):
        raise HTTPException(409, "같은 zone_id가 이미 있습니다.")
    row = Zone(zone_id=payload.zone_id, zone_name=payload.zone_name, coordinates_json="{}")
    assign(row, payload)
    db.add(row)
    db.commit()
    return serialize(row)


@router.put("/{zone_id}")
def update_zone(zone_id: str, payload: ZoneIn, db: Session = Depends(get_db)):
    row = db.get(Zone, zone_id)
    if not row:
        raise HTTPException(404, "위험구역을 찾을 수 없습니다.")
    assign(row, payload)
    db.commit()
    return serialize(row)


@router.delete("/{zone_id}", status_code=204)
def delete_zone(zone_id: str, db: Session = Depends(get_db)):
    row = db.get(Zone, zone_id)
    if not row:
        raise HTTPException(404, "위험구역을 찾을 수 없습니다.")
    db.delete(row)
    db.commit()
    return Response(status_code=204)

