import copy
import json
import math
from pathlib import Path
import sys

from fastapi.testclient import TestClient
import pytest

from app.config import settings
from app.main import app
from app.routers import uwb
from app.services import location_filter_service as smoothing, zone_service
from app.services.location_service import solve_position, PositionSolveError
from app.services.location_speed_service import speed_guard
from app.services.uwb_distance_filter import DistanceFilter
from app.site_profile import default_anchor_positions
from test_uwb_signal_quality import diagnostic

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from uwb_live_bridge import parse_tag_line, raw_measurements, build_cycle_payload
from app.schemas.api import UwbDistancesIn


def payload(cycle=0, bad=()):
    observations, measurements = [], []
    for anchor, (x, y) in default_anchor_positions().items():
        distance = math.hypot(2.2-x, 3.4-y)
        observations.append(dict(anchor_id=anchor, status="valid", raw_distance_m=distance,
                                 diagnostics=diagnostic(15, 12) if anchor in bad else diagnostic()))
        measurements.append(dict(anchor_id=anchor, distance_m=distance, quality=.95))
    return dict(schema_version=2, worker_id="worker-001", helmet_id="helmet-001", device_id="helmet-001-uwb",
                uwb_tag_id="tag-001", session_id="boot-a", measurement_id=f"boot-a:{cycle}", cycle_id=cycle,
                sequence=cycle % 256, measured_uptime_us=cycle*300000, distances_calibrated=False,
                observations=observations, measurements=measurements)


@pytest.fixture
def rig(monkeypatch):
    from app.routers.auth import require_site
    monkeypatch.setitem(app.dependency_overrides, require_site, lambda: "site-001")
    from app.services import uwb_distance_filter
    monkeypatch.setattr(uwb_distance_filter, "calibration_offsets", lambda: {})
    original = DistanceFilter.process
    monkeypatch.setattr(DistanceFilter, "process", lambda self, p: original(self, p, 1000+p.measured_uptime_us/1e6))
    rows = []
    monkeypatch.setattr(uwb, "record_observation", lambda row: rows.append(copy.deepcopy(row)) or True)
    return rows


def test_quality_exclusion_holds_position_age_and_zone_but_communication_succeeds(monkeypatch, rig):
    monkeypatch.setattr(settings, "uwb_quality_mode", "enforce")
    monkeypatch.setattr(settings, "uwb_speed_mode", "enforce")
    bad = ("anchor-001", "anchor-002")
    with TestClient(app) as client:
        for i in range(3):
            result = client.post("/api/uwb/distances", json=payload(i)).json()
        before = result["worker"]
        before_filters = copy.deepcopy((smoothing._history, smoothing._states, zone_service._inside_counts, zone_service._outside_counts))
        reference = copy.deepcopy(speed_guard.states)
        failure = client.post("/api/uwb/distances", json=payload(3, bad))
        assert failure.status_code == 422
        data = failure.json()
        assert isinstance(data["detail"], str) and not data["location"]["changed"]
        assert data["observation"]["position_check"]["reason"] == "insufficient_anchors"
        assert data["observation"]["pipeline"] == dict(communication_received=True, frame_accepted=True,
            distance_usable=True, usable_anchor_count=2, position_solved=False, position_accepted=False, position_applied=False)
        assert data["worker"]["position_status"]["last_valid_at"] == before["position_status"]["last_valid_at"]
        assert data["worker"]["position_status"]["last_valid_age_seconds"] >= 0
        assert (data["worker"]["x"], data["worker"]["y"]) == (before["x"], before["y"])
        assert before_filters == (smoothing._history, smoothing._states, zone_service._inside_counts, zone_service._outside_counts)
        assert speed_guard.states == reference
        snapshot = client.get("/api/dashboard/snapshot").json()
        assert all(a["online"] for a in snapshot["anchors"])
        assert next(d for d in snapshot["devices"] if d["device_id"] == "helmet-001-uwb")["online"]
        for i in (4, 5):
            assert client.post("/api/uwb/distances", json=payload(i)).status_code == 422
        restored = client.post("/api/uwb/distances", json=payload(6))
        assert restored.status_code == 200
        assert restored.json()["observation"]["pipeline"]["position_accepted"]
        for m in restored.json()["observation"]["distance_processing"]["measurements"]:
            if m["anchor_id"] in bad:
                assert m["sample_count"] == 1
    assert rig[3]["filtered_position"] is None


def test_observe_preserves_existing_position_and_weights(monkeypatch, rig):
    with TestClient(app) as client:
        nominal = client.post("/api/uwb/distances", json=payload(0)).json()
        bad = client.post("/api/uwb/distances", json=payload(1, ("anchor-001", "anchor-002"))).json()
    assert bad["observation"]["pipeline"]["usable_anchor_count"] == 4
    assert bad["observation"]["pipeline"]["position_solved"]
    for field in ("raw_x", "raw_y", "confidence"):
        assert nominal["location"][field] == bad["location"][field]
    assert all(m["quality"] == .95 for m in bad["observation"]["distance_processing"]["measurements"])


def test_usb_wifi_full_flow_and_duplicate_do_not_advance_quality_recovery(monkeypatch, rig):
    monkeypatch.setattr(settings, "uwb_quality_mode", "enforce")
    monkeypatch.setattr(settings, "uwb_speed_mode", "enforce")
    with TestClient(app) as client:
        for i in range(3):
            wifi = {**payload(i), "transport": "wifi"}
            frame = parse_tag_line(json.dumps(wifi))
            usb = build_cycle_payload(frame, raw_measurements(frame), "2026-10-15T00:00:00Z")
            response = client.post("/api/uwb/distances", json=usb)
            assert response.status_code == 200
            assert client.post("/api/uwb/distances", json=wifi).json()["observation"]["reason"] == "duplicate_measurement"
            assert all(m["sample_count"] == i+1 for m in response.json()["observation"]["distance_processing"]["measurements"])
        assert response.json()["observation"]["pipeline"]["position_accepted"]


def test_enforced_signal_decisions_identical_for_usb_wifi(tmp_path):
    source = payload(0, ("anchor-001",))
    frame = parse_tag_line(json.dumps(source))
    usb = UwbDistancesIn.model_validate(build_cycle_payload(frame, raw_measurements(frame), "2026-10-15T00:00:00Z"))
    wifi = UwbDistancesIn.model_validate({**source, "transport": "wifi"})
    cfg = settings.model_copy(update={"uwb_quality_mode": "enforce", "uwb_filter_state_path": str(tmp_path/"usb.db")})
    a = DistanceFilter(cfg, {}).process(usb, 100)
    cfg = cfg.model_copy(update={"uwb_filter_state_path": str(tmp_path/"wifi.db")})
    assert a == DistanceFilter(cfg, {}).process(wifi, 100)


def square():
    return [dict(anchor_id=str(i), x=x, y=y) for i, (x, y) in enumerate(((0, 0), (4, 0), (4, 4), (0, 4)))]


def test_solver_explicit_exclusion_is_separate_from_minimum_weight():
    anchors = square()
    measurements = [dict(anchor_id=a["anchor_id"], distance_m=math.hypot(1.2-a["x"], 2.3-a["y"]), quality=1) for a in anchors]
    measurements[0].update(distance_m=80, excluded=True)
    x, y, _ = solve_position(anchors, measurements)
    assert (x, y) == pytest.approx((1.2, 2.3), abs=.01)
    measurements[1]["excluded"] = True
    with pytest.raises(PositionSolveError, match="3개 미만"):
        solve_position(anchors, measurements)
    # quality=0 alone remains the legacy minimum-weight contract, not exclusion.
    measurements = [dict(anchor_id=a["anchor_id"], distance_m=math.hypot(1.2-a["x"], 2.3-a["y"]), quality=0) for a in anchors]
    assert solve_position(anchors, measurements)[:2] == pytest.approx((1.2, 2.3), abs=.01)


def test_solver_instability_checks_and_distinct_anchors():
    anchors = [dict(anchor_id=str(i), x=i, y=0) for i in range(3)]
    with pytest.raises(PositionSolveError) as failure:
        solve_position(anchors, [dict(anchor_id=str(i), distance_m=2) for i in range(3)])
    assert failure.value.reason == "singular_geometry"
    with pytest.raises(PositionSolveError) as failure:
        solve_position(square(), [dict(anchor_id=str(i), distance_m=10) for i in range(4)])
    assert failure.value.reason == "high_residual"
    with pytest.raises(PositionSolveError) as failure:
        solve_position(square(), [dict(anchor_id="0", distance_m=2)]*3)
    assert failure.value.reason == "insufficient_anchors"
    with pytest.raises(PositionSolveError) as failure:
        solve_position(square(), [dict(anchor_id=str(i), distance_m=d) for i, d in enumerate((1.13, 4.32, 9.22, 8.1))])
    assert failure.value.reason == "nonconverged"


def test_api_unstable_geometry_holds_position_in_observe_mode(monkeypatch, rig):
    from app.database import SessionLocal
    from app.models.entities import Anchor
    with TestClient(app) as client:
        before = client.get("/api/locations/worker-001/latest").json()
        with SessionLocal() as db:
            anchors = db.query(Anchor).order_by(Anchor.anchor_id).all()
            coordinates = [(a.anchor_id, a.x, a.y) for a in anchors]
            for i, a in enumerate(anchors):
                a.x, a.y = i, 0
            db.commit()
        try:
            response = client.post("/api/uwb/distances", json=payload())
            assert response.status_code == 422
            data = response.json()
            assert data["worker"]["position_status"]["reason"] == "singular_geometry"
            assert data["worker"]["position_status"]["last_valid_at"] == before["position_status"]["last_valid_at"]
            assert (data["location"]["x"], data["location"]["y"]) == (before["x"], before["y"])
        finally:
            with SessionLocal() as db:
                for anchor, x, y in coordinates:
                    a = db.get(Anchor, anchor)
                    a.x, a.y = x, y
                db.commit()


def test_suspect_weight_is_used_by_existing_solver(tmp_path):
    data = payload()
    data["observations"][-1]["raw_distance_m"] += .8
    data["observations"][-1]["diagnostics"] = diagnostic(8, 5)
    data["measurements"][-1]["distance_m"] += .8
    p = UwbDistancesIn.model_validate(data)
    anchors = [dict(anchor_id=a, x=xy[0], y=xy[1]) for a, xy in default_anchor_positions().items()]
    errors = {}
    for mode in ("observe", "enforce"):
        cfg = settings.model_copy(update={"uwb_quality_mode": mode, "uwb_filter_state_path": str(tmp_path/f"{mode}.db")})
        processed = DistanceFilter(cfg, {}).process(p, 100)
        x, y, _ = solve_position(anchors, processed["measurements"])
        errors[mode] = math.hypot(x-2.2, y-3.4)
    assert errors["enforce"] < errors["observe"]  # Synthetic case only; not a field accuracy claim.


def test_last_valid_position_survives_observed_jump_failure_and_restart(monkeypatch, rig):
    monkeypatch.setattr(uwb, "solve_position", lambda *args: (2.2, 3.4, .9))
    with TestClient(app) as client:
        for i in range(3):
            result = client.post("/api/uwb/distances", json=payload(i)).json()
        valid = result["worker"]["position_status"]["last_valid_position"]
        assert valid is not None
        monkeypatch.setattr(uwb, "solve_position", lambda *args: (100, 100, .9))
        jumped = client.post("/api/uwb/distances", json=payload(3)).json()
        assert not jumped["observation"]["position_accepted"]
        assert jumped["worker"]["position_status"]["last_valid_position"] == valid
        def fail(*args):
            raise PositionSolveError("insufficient_anchors", "test: fewer than three anchors")
        monkeypatch.setattr(uwb, "solve_position", fail)
        held = client.post("/api/uwb/distances", json=payload(4)).json()
        assert held["worker"]["position_status"]["last_valid_position"] == valid
    with TestClient(app) as client:
        assert client.get("/api/locations/worker-001/latest").json()["position_status"]["last_valid_position"] == valid
