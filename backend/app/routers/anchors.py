from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.entities import Anchor
from ..schemas.api import AnchorIn

router = APIRouter(prefix="/api/anchors", tags=["anchors"])


def serialize(row: Anchor) -> dict:
    return {"anchor_id": row.anchor_id, "name": row.name, "x": row.x, "y": row.y, "z": row.z, "online": row.online, "last_seen": row.last_seen.isoformat() + "Z"}


@router.get("")
def list_anchors(db: Session = Depends(get_db)):
    return [serialize(row) for row in db.query(Anchor).order_by(Anchor.anchor_id).all()]


@router.post("")
def create_anchor(payload: AnchorIn, db: Session = Depends(get_db)):
    if db.get(Anchor, payload.anchor_id):
        raise HTTPException(409, "같은 anchor_id가 이미 있습니다.")
    row = Anchor(**payload.model_dump())
    db.add(row)
    db.commit()
    return serialize(row)


@router.put("/{anchor_id}")
def update_anchor(anchor_id: str, payload: AnchorIn, db: Session = Depends(get_db)):
    row = db.get(Anchor, anchor_id)
    if not row:
        raise HTTPException(404, "앵커를 찾을 수 없습니다.")
    for key, value in payload.model_dump(exclude={"anchor_id"}).items():
        setattr(row, key, value)
    db.commit()
    return serialize(row)


@router.delete("/{anchor_id}", status_code=204)
def delete_anchor(anchor_id: str, db: Session = Depends(get_db)):
    row = db.get(Anchor, anchor_id)
    if not row:
        raise HTTPException(404, "앵커를 찾을 수 없습니다.")
    db.delete(row)
    db.commit()
    return Response(status_code=204)

