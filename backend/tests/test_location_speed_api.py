import copy
from datetime import timedelta
import json

from fastapi.testclient import TestClient
import pytest

from app.config import settings
from app.database import SessionLocal, utcnow
from app.main import app
from app.models.entities import Device, WorkerState
from app.routers import uwb
from app.services import location_filter_service as smoothing, zone_service
from app.services.location_speed_service import speed_guard
from app.services.uwb_distance_filter import DistanceFilter


def packet(cycle, **extra):
    data = dict(schema_version=2, worker_id="worker-001", helmet_id="helmet-001", device_id="helmet-001-uwb",
                uwb_tag_id="tag-001", session_id="boot-a", measurement_id=f"boot-a:{cycle}", cycle_id=cycle,
                sequence=cycle % 256, measured_uptime_us=cycle*300000, distances_calibrated=False,
                measurements=[dict(anchor_id=f"anchor-{i:03d}", distance_m=3) for i in range(1, 5)])
    data.update(extra)
    return data


@pytest.fixture
def rig(monkeypatch):
    rows = []
    monkeypatch.setattr(uwb, "record_observation", lambda row: rows.append(copy.deepcopy(row)) or True)
    original = DistanceFilter.process
    monkeypatch.setattr(DistanceFilter, "process", lambda self, p: original(self, p, now=1000+p.measured_uptime_us/1e6))
    return rows


def test_enforcement_never_contaminates_smoothing_clamp_zone_or_risk(monkeypatch, rig):
    monkeypatch.setattr(settings, "uwb_speed_mode", "enforce")
    candidates = iter([(2, 2)]*3+[(100, 100), (2.05, 2)])
    monkeypatch.setattr(uwb, "solve_position", lambda *args: (*next(candidates), .9))
    counts = dict(filter=0, clamp=0, zone=0, risk=0)
    for name, label in (("filter_location", "filter"), ("clamp_position", "clamp"), ("confirm_zone", "zone"), ("recalculate_risk", "risk")):
        original = getattr(uwb, name)
        def wrap(*args, _label=label, _original=original, **kwargs):
            counts[_label] += 1
            return _original(*args, **kwargs)
        monkeypatch.setattr(uwb, name, wrap)
    with TestClient(app) as client:
        first = [client.post("/api/uwb/distances", json=packet(i)).json() for i in range(3)]
        assert [r["observation"]["position_accepted"] for r in first] == [False, False, True]
        snapshot = copy.deepcopy((smoothing._history, smoothing._states, zone_service._inside_counts, zone_service._outside_counts))
        before_counts = counts.copy()
        before_worker = first[-1]["worker"]
        rejected = client.post("/api/uwb/distances", json=packet(3)).json()
        assert rejected["observation"]["position_check"]["reason"] == "speed_exceeded"
        assert not rejected["location"]["changed"]
        assert counts == before_counts
        assert snapshot == (smoothing._history, smoothing._states, zone_service._inside_counts, zone_service._outside_counts)
        for field in ("x", "y", "confidence", "current_zone", "risk_score", "risk_level"):
            assert rejected["worker"][field] == before_worker[field]
        assert rejected["worker"]["position_status"]["last_valid_at"] == before_worker["position_status"]["last_valid_at"]
        assert rejected["observation"]["distance_processing"]["measurements"][0]["sample_count"] == 4
        assert rig[-1]["candidate_position"] == {"x": 100, "y": 100}
        assert rig[-1]["filtered_position"] is None
        assert rig[-1]["position_check"]["allowed_distance_m"] == pytest.approx(1.9)
        with SessionLocal() as db:
            device = db.get(Device, "helmet-001-uwb")
            assert device.online and device.last_uwb_at is not None
        returned = client.post("/api/uwb/distances", json=packet(4)).json()
        assert returned["observation"]["position_accepted"]


def test_observe_preserves_existing_coordinate_flow(monkeypatch, rig):
    candidates = iter([(2, 2)]*3+[(100, 100)])
    monkeypatch.setattr(uwb, "solve_position", lambda *args: (*next(candidates), .9))
    seen = []
    monkeypatch.setattr(uwb, "filter_location", lambda worker, x, y, previous: seen.append((x, y)) or (x, y))
    with TestClient(app) as client:
        results = [client.post("/api/uwb/distances", json=packet(i)).json() for i in range(4)]
    assert len(seen) == 4 and seen[-1] == (100, 100)
    check = results[-1]["observation"]["position_check"]
    assert check["applied"] and not check["accepted"]
    assert rig[-1]["status"] == "computed"


def test_stationary_valid_age_duplicates_and_failed_solve(monkeypatch, rig):
    monkeypatch.setattr(settings, "uwb_speed_mode", "enforce")
    monkeypatch.setattr(uwb, "solve_position", lambda *args: (2, 2, .9))
    with TestClient(app) as client:
        for i in range(4):
            result = client.post("/api/uwb/distances", json=packet(i)).json()
        assert result["observation"]["position_accepted"] and not result["location"]["changed"]
        with SessionLocal() as db:
            worker = db.get(WorkerState, "worker-001")
            worker.last_valid_location_at = utcnow()-timedelta(seconds=20)
            db.commit()
        before = client.get("/api/locations/worker-001/latest").json()
        assert before["position_status"]["last_valid_age_seconds"] >= 20
        duplicate = client.post("/api/uwb/distances", json=packet(3)).json()
        assert duplicate["observation"]["reason"] == "duplicate_measurement"
        assert duplicate["worker"]["position_status"]["last_valid_at"] == before["position_status"]["last_valid_at"]
        def fail(*args):
            raise ValueError("test: insufficient geometry")
        monkeypatch.setattr(uwb, "solve_position", fail)
        assert client.post("/api/uwb/distances", json=packet(4)).status_code == 422
        snapshot = client.get("/api/dashboard/snapshot").json()
        worker = next(w for w in snapshot["workers"] if w["worker_id"] == "worker-001")
        device = next(d for d in snapshot["devices"] if d["device_id"] == "helmet-001-uwb")
        assert device["online"] and device["last_uwb_at"] is not None
        assert worker["position_status"]["last_valid_at"] == before["position_status"]["last_valid_at"]
        assert worker["position_status"]["reason"] == "solve_failed"


def test_reacquisition_resets_smoothing_and_restart_keeps_valid_age(monkeypatch, rig):
    monkeypatch.setattr(settings, "uwb_speed_mode", "enforce")
    candidates = iter([(2, 2)]*3+[(100, 100)]*8)
    monkeypatch.setattr(uwb, "solve_position", lambda *args: (*next(candidates), .9))
    with TestClient(app) as client:
        for i in range(11):
            result = client.post("/api/uwb/distances", json=packet(i)).json()
        assert result["observation"]["position_check"]["reason"] == "reacquired_after_rejections"
        assert list(smoothing._history["worker-001"]) == [(100, 100)]
        last_valid = result["worker"]["position_status"]["last_valid_at"]
    # Restart clears the provisional/accepted speed reference, not the persisted last-valid timestamp.
    with TestClient(app) as client:
        assert speed_guard.states == {}
        latest = client.get("/api/locations/worker-001/latest").json()
        assert latest["position_status"]["last_valid_at"] == last_valid
        assert latest["position_status"]["reason"] == "server_restart_acquisition"


def test_stationary_screen_does_not_become_speed_reference(monkeypatch, rig):
    monkeypatch.setattr(settings, "uwb_speed_mode", "enforce")
    candidates = iter([(2, 2)]*3+[(2.1, 2), (2.2, 2), (2.3, 2)])
    monkeypatch.setattr(uwb, "solve_position", lambda *args: (*next(candidates), .9))
    with TestClient(app) as client:
        results = [client.post("/api/uwb/distances", json=packet(i)).json() for i in range(6)]
    assert results[3]["location"]["x"] == 2
    assert results[4]["location"]["x"] == 2
    assert results[4]["observation"]["position_check"]["reference"]["x"] == 2.1
    assert all(r["observation"]["position_accepted"] for r in results[2:])


def test_existing_database_upgrade_preserves_worker_position(monkeypatch, tmp_path):
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.orm import sessionmaker
    from app import database
    engine = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    local = sessionmaker(bind=engine, expire_on_commit=False)
    database.Base.metadata.create_all(bind=engine)
    with local() as db:
        db.add(WorkerState(worker_id="worker-001", helmet_id="helmet-001", x=3.2, y=4.1))
        db.commit()
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE worker_states DROP COLUMN last_valid_location_at"))
        connection.execute(text("ALTER TABLE worker_states DROP COLUMN last_valid_location_json"))
        connection.execute(text("ALTER TABLE worker_states DROP COLUMN position_status_json"))
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", local)
    try:
        database.init_database()
        columns = {c["name"] for c in inspect(engine).get_columns("worker_states")}
        assert {"last_valid_location_at", "last_valid_location_json", "position_status_json"} <= columns
        with local() as db:
            worker = db.get(WorkerState, "worker-001")
            assert (worker.x, worker.y) == (3.2, 4.1)
            assert worker.last_valid_location_at is None
            assert worker.last_valid_location_json == "null"
    finally:
        engine.dispose()


def test_nonfinite_candidate_is_logged_as_invalid_without_poisoning_state(monkeypatch, rig):
    monkeypatch.setattr(uwb, "solve_position", lambda *args: (float("nan"), 2, .9))
    with TestClient(app) as client:
        response = client.post("/api/uwb/distances", json=packet(0))
    assert response.status_code == 200
    assert response.json()["observation"]["position_check"]["reason"] == "nonfinite_candidate"
    assert response.json()["location"]["raw_x"] is None
    assert rig[-1]["candidate_position"]["x"] is None
