from contextlib import contextmanager
from datetime import datetime, timezone
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_database() -> None:
    from .models.entities import Anchor, Device, WorkerState, Zone

    Base.metadata.create_all(bind=engine)
    with session_scope() as db:
        if not db.get(WorkerState, "worker-001"):
            db.add(
                WorkerState(
                    worker_id="worker-001",
                    worker_name="한미르 작업자",
                    helmet_id="helmet-001",
                    x=2.0,
                    y=2.0,
                    confidence=0.92,
                    risk_score=0,
                    risk_level="정상",
                    reasons_json="[]",
                    ppe_json=json.dumps({"vest": True, "glove": True}),
                    hazard_json=json.dumps({"fire": False, "smoke": False}),
                )
            )
        for device_id, device_type in (
            ("helmet-001-av", "assistant_device"),
            ("helmet-001-uwb", "position_device"),
        ):
            if not db.get(Device, device_id):
                db.add(
                    Device(
                        device_id=device_id,
                        device_type=device_type,
                        organization_id="org-001",
                        site_id="site-001",
                        worker_id="worker-001",
                        helmet_id="helmet-001",
                        battery=86,
                        online=True,
                        component_status_json=json.dumps(
                            {"camera": "ready", "mic": "ready", "speaker": "ready", "button": "ready", "uwb": "ready"}
                        ),
                    )
                )
        anchors = {
            "anchor-001": (0.0, 0.0),
            "anchor-002": (12.0, 0.0),
            "anchor-003": (12.0, 8.0),
            "anchor-004": (0.0, 8.0),
        }
        for anchor_id, (x, y) in anchors.items():
            if not db.get(Anchor, anchor_id):
                db.add(Anchor(anchor_id=anchor_id, name=anchor_id, x=x, y=y, z=2.2, online=True))
        if not db.get(Zone, "zone-hot-work"):
            db.add(
                Zone(
                    zone_id="zone-hot-work",
                    zone_name="화기 작업 위험구역",
                    zone_type="rectangle",
                    coordinates_json=json.dumps({"x": 7.0, "y": 2.0, "width": 4.0, "height": 4.0}),
                    required_ppe_json=json.dumps(["vest", "glove"]),
                    risk_weight=30,
                    warning_message="화기 작업 위험구역에 진입했습니다.",
                    max_stay_seconds=120,
                    active=True,
                )
            )

