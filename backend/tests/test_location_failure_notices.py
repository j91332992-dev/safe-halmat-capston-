from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.config import settings
from app.models.entities import Event
from app.services import location_failure_notice_service as notices


@pytest.fixture
def clock(monkeypatch):
    value = {"t": 0.0}
    start = datetime(2026, 10, 25, 0, 0, 0)
    notices._last_notices.clear()
    monkeypatch.setattr(settings, "uwb_location_failure_notice_seconds", 600.0)
    monkeypatch.setattr(notices.time, "monotonic", lambda: value["t"])
    monkeypatch.setattr(notices, "utcnow", lambda: start + timedelta(seconds=value["t"]))
    return value, start


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Event.__table__.create(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def emit(db, clock, reason="nonconverged", worker="worker-1", site="site-1"):
    value, start = clock
    result = notices.create_location_failure_notice(db, reason, worker, "tag-1", site)
    if result:
        result.created_at = start + timedelta(seconds=value["t"])
    db.commit()
    return result


def test_alternating_reasons_share_ten_minute_window(db, clock):
    assert emit(db, clock) is not None
    clock[0]["t"] = 5
    assert emit(db, clock, "insufficient_anchors") is None
    clock[0]["t"] = 599.999
    assert emit(db, clock) is None
    clock[0]["t"] = 600
    assert emit(db, clock, "insufficient_anchors") is not None
    assert db.query(Event).count() == 2


def test_restart_preserves_remaining_cooldown(db, clock):
    emit(db, clock)
    clock[0]["t"] = 300
    notices._last_notices.clear()
    assert emit(db, clock) is None
    clock[0]["t"] = 600
    assert emit(db, clock) is not None


def test_workers_and_sites_do_not_suppress_each_other(db, clock):
    assert emit(db, clock) is not None
    assert emit(db, clock, worker="worker-2") is not None
    assert emit(db, clock, site="site-2") is not None
    assert db.query(Event).count() == 3


def test_suppressed_cycles_do_not_query_database_each_time(db, clock):
    emit(db, clock)
    statements = []
    def record(conn, cursor, statement, parameters, context, many):
        statements.append(statement)
    event.listen(db.bind, "before_cursor_execute", record)
    for i in range(1000):
        clock[0]["t"] = (i + 1) / 10
        assert emit(db, clock, str(i % 2)) is None
    assert not any(s.lstrip().upper().startswith("SELECT") for s in statements)
