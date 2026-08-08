import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db, utcnow
from ..models.entities import Anchor, LayoutDraft, LayoutVersion, Obstacle, SiteLayout, Zone
from ..schemas.api import LayoutDraftIn, LayoutVersionCreate, ObstacleIn, SiteLayoutIn

router = APIRouter(prefix="/api/layout", tags=["layout"])


def anchor_dict(row: Anchor) -> dict:
    return {"anchor_id": row.anchor_id, "name": row.name, "x": row.x, "y": row.y, "z": row.z, "online": row.online}


def obstacle_dict(row: Obstacle) -> dict:
    return {"obstacle_id": row.obstacle_id, "object_type": row.object_type, "name": row.name, "x": row.x, "y": row.y, "width": row.width, "height": row.height}


def zone_dict(row: Zone) -> dict:
    return {
        "zone_id": row.zone_id,
        "zone_name": row.zone_name,
        "zone_type": row.zone_type,
        "zone_category": row.zone_category,
        "coordinates": json.loads(row.coordinates_json),
        "required_ppe": json.loads(row.required_ppe_json),
        "allowed_worker_ids": json.loads(row.allowed_worker_ids_json),
        "risk_weight": row.risk_weight,
        "warning_message": row.warning_message,
        "max_stay_seconds": row.max_stay_seconds,
        "active": row.active,
    }


def current_layout(db: Session) -> SiteLayout:
    row = db.get(SiteLayout, settings.site_id)
    if not row:
        row = SiteLayout(site_id=settings.site_id, name=settings.site_name, width=settings.site_width_m, height=settings.site_height_m)
        db.add(row)
        db.flush()
    return row


def fit_obstacle(payload: ObstacleIn, layout: SiteLayout) -> dict:
    width = min(payload.width, layout.width)
    height = min(payload.height, layout.height)
    return {
        "name": payload.name,
        "object_type": payload.object_type,
        "x": min(payload.x, max(0.0, layout.width - width)),
        "y": min(payload.y, max(0.0, layout.height - height)),
        "width": width,
        "height": height,
    }


def applied_design(db: Session) -> dict:
    layout = current_layout(db)
    return {
        "site": {"name": layout.name, "width": layout.width, "height": layout.height},
        "anchors": [anchor_dict(row) for row in db.query(Anchor).order_by(Anchor.anchor_id).all()],
        "obstacles": [obstacle_dict(row) for row in db.query(Obstacle).filter(Obstacle.site_id == layout.site_id).all()],
        "zones": [zone_dict(row) for row in db.query(Zone).all()],
    }


@router.get("")
def get_layout(db: Session = Depends(get_db)):
    result = applied_design(db)
    db.commit()
    return result


@router.get("/draft")
def get_draft(db: Session = Depends(get_db)):
    row = db.get(LayoutDraft, settings.site_id)
    if row:
        return {**json.loads(row.draft_json), "saved_at": row.updated_at.isoformat() + "Z"}
    result = applied_design(db)
    db.commit()
    return {**result, "saved_at": None}


@router.put("/draft")
def save_draft(payload: LayoutDraftIn, db: Session = Depends(get_db)):
    row = db.get(LayoutDraft, settings.site_id)
    data = json.dumps(payload.model_dump(), ensure_ascii=False)
    if row:
        row.draft_json = data
        row.updated_at = utcnow()
    else:
        row = LayoutDraft(site_id=settings.site_id, draft_json=data, updated_at=utcnow())
        db.add(row)
    db.commit()
    return {"saved": True, "saved_at": row.updated_at.isoformat() + "Z"}


@router.post("/apply")
def apply_draft(db: Session = Depends(get_db)):
    draft = db.get(LayoutDraft, settings.site_id)
    if not draft:
        raise HTTPException(404, "저장된 설계안이 없습니다.")
    payload = LayoutDraftIn.model_validate(json.loads(draft.draft_json))
    layout = current_layout(db)
    layout.name = payload.site.name
    layout.width = payload.site.width
    layout.height = payload.site.height

    for item in payload.anchors:
        row = db.get(Anchor, item.anchor_id)
        if row:
            for key, value in item.model_dump(exclude={"anchor_id", "online"}).items():
                setattr(row, key, value)
        else:
            db.add(Anchor(**item.model_dump(exclude={"online"}), online=False))

    keep_obstacle_ids = {item.obstacle_id for item in payload.obstacles}
    obstacle_query = db.query(Obstacle).filter(Obstacle.site_id == layout.site_id)
    if keep_obstacle_ids:
        obstacle_query.filter(Obstacle.obstacle_id.notin_(keep_obstacle_ids)).delete(synchronize_session=False)
    else:
        obstacle_query.delete(synchronize_session=False)
    for item in payload.obstacles:
        row = db.get(Obstacle, item.obstacle_id)
        values = fit_obstacle(item, layout)
        if row:
            for key, value in values.items():
                setattr(row, key, value)
        else:
            db.add(Obstacle(obstacle_id=item.obstacle_id, site_id=layout.site_id, **values))

    keep_zone_ids = {item.zone_id for item in payload.zones}
    if keep_zone_ids:
        db.query(Zone).filter(Zone.zone_id.notin_(keep_zone_ids)).delete(synchronize_session=False)
    else:
        db.query(Zone).delete()
    for item in payload.zones:
        row = db.get(Zone, item.zone_id)
        if not row:
            row = Zone(zone_id=item.zone_id, zone_name=item.zone_name, coordinates_json="{}")
            db.add(row)
        row.zone_name = item.zone_name
        row.zone_type = item.zone_type
        row.zone_category = item.zone_category
        row.coordinates_json = json.dumps(item.coordinates)
        row.required_ppe_json = json.dumps(item.required_ppe)
        row.allowed_worker_ids_json = json.dumps(item.allowed_worker_ids)
        row.risk_weight = item.risk_weight
        row.warning_message = item.warning_message
        row.max_stay_seconds = item.max_stay_seconds
        row.active = item.active

    db.commit()
    return {"applied": True, "design": applied_design(db)}


@router.put("/site")
def update_site(payload: SiteLayoutIn, db: Session = Depends(get_db)):
    layout = current_layout(db)
    layout.name = payload.name
    layout.width = payload.width
    layout.height = payload.height
    db.commit()
    return {"site_id": layout.site_id, "name": layout.name, "width": layout.width, "height": layout.height}


@router.post("/obstacles")
def create_obstacle(payload: ObstacleIn, db: Session = Depends(get_db)):
    if db.get(Obstacle, payload.obstacle_id):
        raise HTTPException(409, "같은 장애물 ID가 이미 있습니다.")
    layout = current_layout(db)
    row = Obstacle(obstacle_id=payload.obstacle_id, site_id=layout.site_id, **fit_obstacle(payload, layout))
    db.add(row)
    db.commit()
    return obstacle_dict(row)


@router.put("/obstacles/{obstacle_id}")
def update_obstacle(obstacle_id: str, payload: ObstacleIn, db: Session = Depends(get_db)):
    row = db.get(Obstacle, obstacle_id)
    if not row:
        raise HTTPException(404, "장애물을 찾을 수 없습니다.")
    layout = current_layout(db)
    for key, value in fit_obstacle(payload, layout).items():
        setattr(row, key, value)
    db.commit()
    return obstacle_dict(row)


@router.delete("/obstacles/{obstacle_id}", status_code=204)
def delete_obstacle(obstacle_id: str, db: Session = Depends(get_db)):
    row = db.get(Obstacle, obstacle_id)
    if not row:
        raise HTTPException(404, "장애물을 찾을 수 없습니다.")
    db.delete(row)
    db.commit()
    return Response(status_code=204)


@router.get("/versions")
def list_versions(db: Session = Depends(get_db)):
    rows = db.query(LayoutVersion).filter(LayoutVersion.site_id == settings.site_id).order_by(LayoutVersion.created_at.desc()).all()
    return [{"version_id": row.version_id, "name": row.name, "created_at": row.created_at.isoformat() + "Z"} for row in rows]


@router.post("/versions")
def create_version(payload: LayoutVersionCreate, db: Session = Depends(get_db)):
    draft = db.get(LayoutDraft, settings.site_id)
    if not draft:
        raise HTTPException(400, "버전으로 저장할 설계안을 먼저 저장하세요.")
    row = LayoutVersion(
        version_id="layout-" + uuid4().hex,
        site_id=settings.site_id,
        name=payload.name,
        design_json=draft.draft_json,
    )
    db.add(row)
    db.commit()
    return {"version_id": row.version_id, "name": row.name, "created_at": row.created_at.isoformat() + "Z"}


@router.post("/versions/{version_id}/load")
def load_version(version_id: str, db: Session = Depends(get_db)):
    version = db.get(LayoutVersion, version_id)
    if not version:
        raise HTTPException(404, "설계 버전을 찾을 수 없습니다.")
    draft = db.get(LayoutDraft, settings.site_id)
    if draft:
        draft.draft_json = version.design_json
        draft.updated_at = utcnow()
    else:
        draft = LayoutDraft(site_id=settings.site_id, draft_json=version.design_json, updated_at=utcnow())
        db.add(draft)
    db.commit()
    return {**json.loads(version.design_json), "saved_at": draft.updated_at.isoformat() + "Z"}


@router.delete("/versions/{version_id}", status_code=204)
def delete_version(version_id: str, db: Session = Depends(get_db)):
    row = db.get(LayoutVersion, version_id)
    if not row:
        raise HTTPException(404, "설계 버전을 찾을 수 없습니다.")
    db.delete(row)
    db.commit()
    return Response(status_code=204)


