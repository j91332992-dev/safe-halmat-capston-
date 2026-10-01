from contextlib import contextmanager
from datetime import datetime, timezone
import json

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings
from .site_profile import default_anchor_positions


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False, "timeout": 30} if settings.database_url.startswith("sqlite") else {},
)


if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


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
    from .models.entities import Anchor, Device, EvacuationIncident, Event, Obstacle, SiteLayout, WorkerState, Zone

    Base.metadata.create_all(bind=engine)

    if "allowed_worker_ids_json" not in {column["name"] for column in inspect(engine).get_columns("zones")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE zones ADD COLUMN allowed_worker_ids_json TEXT NOT NULL DEFAULT '[]'"))

    if "notes" not in {column["name"] for column in inspect(engine).get_columns("worker_states")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE worker_states ADD COLUMN notes TEXT NOT NULL DEFAULT ''"))

    if "worker_role" not in {column["name"] for column in inspect(engine).get_columns("worker_states")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE worker_states ADD COLUMN worker_role TEXT NOT NULL DEFAULT 'general_worker'"))

    if "zone_category" not in {column["name"] for column in inspect(engine).get_columns("zones")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE zones ADD COLUMN zone_category TEXT NOT NULL DEFAULT 'danger'"))

    if "object_type" not in {column["name"] for column in inspect(engine).get_columns("obstacles")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE obstacles ADD COLUMN object_type TEXT NOT NULL DEFAULT 'obstacle'"))

    if "last_speaker_at" not in {column["name"] for column in inspect(engine).get_columns("devices")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE devices ADD COLUMN last_speaker_at DATETIME"))

    with session_scope() as db:
        if not db.get(SiteLayout, settings.site_id):
            db.add(SiteLayout(site_id=settings.site_id, name=settings.site_name, width=settings.site_width_m, height=settings.site_height_m))
        if not db.get(WorkerState, "worker-001"):
            db.add(
                WorkerState(
                    worker_id="worker-001",
                    worker_name="한미르 작업자",
                    worker_role="general_worker",
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
                        battery=None,
                        online=False,
                        component_status_json="{}",
                    )
                )
        if not db.query(Obstacle).filter(Obstacle.site_id == settings.site_id, Obstacle.object_type == "emergency_exit").first():
            db.add(
                Obstacle(
                    obstacle_id="exit-main",
                    site_id=settings.site_id,
                    name="주 비상구",
                    object_type="emergency_exit",
                    x=max(0.0, settings.site_width_m - 0.8),
                    y=0.0,
                    width=0.8,
                    height=0.25,
                )
            )
        anchors = default_anchor_positions()

        for anchor_id, (x, y) in anchors.items():
            if not db.get(Anchor, anchor_id):
                db.add(Anchor(anchor_id=anchor_id, name=anchor_id, x=x, y=y, z=2.2, online=False))
        # 운영 서버는 시작할 때 모든 연결 상태를 초기화합니다.
        # 이후 실제 heartbeat/프레임/음성/UWB 수신이 온 장치만 온라인이 됩니다.
        db.query(Device).update({Device.online: False}, synchronize_session=False)
        db.query(Anchor).update({Anchor.online: False}, synchronize_session=False)
        db.query(Event).filter(Event.event_type.like("MOCK_%")).delete(synchronize_session=False)
        db.query(EvacuationIncident).filter(EvacuationIncident.source == "mock").delete(synchronize_session=False)

        if not db.get(Zone, "zone-hot-work"):
            db.add(
                Zone(
                    zone_id="zone-hot-work",
                    zone_name="화기 작업 위험구역",
                    zone_type="rectangle",
                    zone_category="danger",
                    coordinates_json=json.dumps({"x": 4.0, "y": 5.5, "width": 1.5, "height": 2.0}),
                    required_ppe_json=json.dumps(["vest", "glove"]),
                    risk_weight=30,
                    warning_message="화기 작업 위험구역에 진입했습니다.",
                    max_stay_seconds=120,
                    active=True,
                )
            )





