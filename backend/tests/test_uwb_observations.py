import copy
import json
import time
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.legacy_uwb_processing import DistanceProcessor
from uwb_live_bridge import (parse_tag_line, build_cycle_payload,
                             build_parser, capture_frames, run_bridge)
from app.schemas.api import UwbDiagnostics, UwbDistancesIn
from app.services.uwb_log_service import BoundedJsonlLog


@pytest.fixture
def packet():
    diagnostic = {
        "status": "valid", "direction": "anchor_to_tag", "sequence": "ipatov",
        "rx_power_dbm": -70.1, "first_path_power_dbm": -72.5,
        "power_difference_db": 2.4, "peak_minus_first_path_samples": 1.25,
        "clock_offset_ppm": -4.5,
        "raw": {"ipatov_power": 200, "ipatov_f1": 40000, "ipatov_f2": 42000,
                "ipatov_f3": 38000, "ipatov_fp_index": 48000, "ipatov_peak": 1577000000,
                "ipatov_accum_count": 128, "dgc_debug": 268435456, "clock_offset": -302},
    }
    return {
        "schema_version": 2, "session_id": "mac-boot1-nonce1", "cycle_id": 255,
        "firmware_version": "uwb-capture-20261015.1", "source_revision": "722c9fd+uwb-log-20261015.1",
        "measurement_id": "mac-boot1-nonce1:255", "sequence": 255, "tag_hw_id": 0,
        "measured_uptime_us": 1000000, "time_basis": "device_monotonic_us", "measured_at": None,
        "worker_id": "worker-001", "helmet_id": "helmet-001",
        "device_id": "helmet-001-uwb", "uwb_tag_id": "tag-001", "distances_calibrated": False,
        "observations": [
            {"anchor_id": f"anchor-{i:03d}", "anchor_hw_id": 159+i,
             "status": "valid", "raw_distance_m": d / 100, "legacy_range_cm": d,
             "measured_uptime_us": 1000000+i*5000, "rx_timestamp_dtu": 1200000000+i,
             "diagnostics": copy.deepcopy(diagnostic)} for i, d in enumerate((450, 510, 560, 470), 1)
        ],
        "measurements": [{"anchor_id": f"anchor-{i:03d}", "distance_m": d, "quality": 0.95}
                         for i, d in enumerate((4.5, 5.1, 5.6, 4.7), 1)],
    }


def test_usb_wifi_identity_and_diagnostics(packet):
    wifi = UwbDistancesIn.model_validate({**packet, "transport": "wifi"})
    frame = parse_tag_line(json.dumps(packet))
    assert frame is not None
    usb = UwbDistancesIn.model_validate(build_cycle_payload(frame, frame.payload["measurements"], "2026-10-14T12:00:00Z"))
    for field in ("session_id", "measurement_id", "cycle_id", "sequence", "measured_uptime_us", "observations",
                  "firmware_version", "source_revision"):
        assert getattr(usb, field) == getattr(wifi, field)
    assert frame.payload == packet
    assert usb.measurements == wifi.measurements
    assert wifi.distances_calibrated is False and usb.distances_calibrated is False


@pytest.mark.parametrize("status,reason", [("missing", "no_response"), ("invalid", "zero_accum_count")])
def test_missing_invalid_are_null(packet, status, reason):
    packet["observations"][0]["diagnostics"] = {"status": status, "reason": reason, "raw": {"ipatov_accum_count": 0}}
    frame = parse_tag_line(json.dumps(packet))
    diagnostic = frame.payload["observations"][0]["diagnostics"]
    validated = UwbDiagnostics.model_validate(diagnostic)
    assert validated.rx_power_dbm is None and validated.first_path_power_dbm is None
    assert validated.raw["ipatov_accum_count"] == 0


@pytest.mark.parametrize("bad", [{"status": "valid"}, {"status": "missing", "rx_power_dbm": 0},
                                  {"status": "invalid", "first_path_power_dbm": 0},
                                  {"status": "invalid", "clock_offset_ppm": float("nan")}])
def test_diagnostics_reject_false_normal_and_nonfinite(bad):
    with pytest.raises(ValidationError):
        UwbDiagnostics.model_validate(bad)


def test_wrap_reboot_and_tag_history_isolation(packet):
    processor = DistanceProcessor({}, history_size=5)
    frame = parse_tag_line(json.dumps(packet))
    processor.process(frame)
    packet.update(cycle_id=256, sequence=0, measurement_id=packet["session_id"] + ":256")
    packet["observations"][0].update(raw_distance_m=6, legacy_range_cm=600)
    wrapped = parse_tag_line(json.dumps(packet))
    assert wrapped.sequence == 0 and wrapped.payload["measurement_id"] != frame.payload["measurement_id"]
    assert processor.process(wrapped)[0]["median_distance_m"] == 5.25
    packet.update(session_id="mac-boot2-nonce2", cycle_id=0, sequence=0, measurement_id="mac-boot2-nonce2:0")
    rebooted = parse_tag_line(json.dumps(packet))
    assert processor.process(rebooted)[0]["median_distance_m"] == 6
    packet.update(tag_hw_id=1, session_id="other-tag")
    packet["observations"][0].update(legacy_range_cm=300, raw_distance_m=3)
    assert processor.process(parse_tag_line(json.dumps(packet)))[0]["median_distance_m"] == 3


def test_held_diagnostic_uses_original_source(packet):
    processor = DistanceProcessor({}, history_size=1)
    processor.process(parse_tag_line(json.dumps(packet)))
    previous_id = packet["measurement_id"]
    packet.update(cycle_id=256, sequence=0, measurement_id=packet["session_id"] + ":256")
    packet["observations"][0].update(status="missing", legacy_range_cm=None, raw_distance_m=None,
                                      diagnostics={"status": "missing", "reason": "no_response"})
    frame = parse_tag_line(json.dumps(packet))
    held = processor.process(frame)[0]
    assert held["held"] and held["source_measurement_id"] == previous_id
    assert held["diagnostics"]["status"] == "valid"
    assert frame.payload["observations"][0]["diagnostics"]["status"] == "missing"


def test_log_rotates_bounds_and_expires_by_oldest_record(tmp_path):
    path = tmp_path / "uwb.jsonl"
    log = BoundedJsonlLog(path, max_bytes=1024, backups=2, retention_days=1)
    for cycle in range(12):
        log.append({"cycle": cycle, "data": "x" * 600})
    files = list(tmp_path.glob("uwb.jsonl*"))
    assert len(files) == 3 and all(file.stat().st_size <= 1024 for file in files)
    for file in files:
        file.write_text(json.dumps({"logged_at_unix": time.time() - 2*86400}) + "\n")
    log.append({"fresh": True})
    assert list(tmp_path.glob("uwb.jsonl*")) == [path]
    assert json.loads(path.read_text())["fresh"]
    with pytest.raises(ValueError):
        log.append({"too_large": "x" * 1024})


def test_log_only_collects_failed_and_full_cycles_without_backend(packet, tmp_path):
    class Port:
        def __init__(self):
            empty = {**packet, "observations": [], "measurements": [], "measurement_id": "empty:0"}
            self.lines = iter([json.dumps(empty).encode(), json.dumps(packet).encode()])
        def readline(self):
            try:
                return next(self.lines)
            except StopIteration:
                raise KeyboardInterrupt

    args = build_parser().parse_args(["--log-only"])
    path = tmp_path / "log.jsonl"
    with pytest.raises(KeyboardInterrupt):
        capture_frames(Port(), args, BoundedJsonlLog(path))
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == 2
    assert all(row["delivery"] == "log_only" for row in rows)
    assert rows[0]["payload"]["measurements"] == []


def test_log_only_never_constructs_backend(monkeypatch, tmp_path):
    import uwb_live_bridge as bridge
    def forbidden(*args, **kwargs):
        pytest.fail("backend must not be constructed in log-only mode")
    monkeypatch.setattr(bridge, "BackendClient", forbidden)
    def stop(*args, **kwargs):
        raise KeyboardInterrupt
    monkeypatch.setattr(bridge.serial, "Serial", stop)
    args = build_parser().parse_args(["--log-only", "--log-path", str(tmp_path / "log.jsonl")])
    with pytest.raises(KeyboardInterrupt):
        run_bridge(args)


def test_slow_http_does_not_block_serial_capture(packet, tmp_path):
    from threading import Event
    started, release = Event(), Event()
    class Backend:
        def heartbeat_if_due(self):
            pass
        def send_payload(self, payload):
            started.set()
            assert release.wait(5)
            return {"observation": {"measurement_id": payload["measurement_id"]}}
    class Port:
        count = 0
        def readline(self):
            self.count += 1
            if self.count == 2:
                assert started.wait(2)
            if self.count > 40:
                release.set()
                raise KeyboardInterrupt
            data = {**packet, "cycle_id": self.count, "measurement_id": f"session:{self.count}"}
            return json.dumps(data).encode()
    path = tmp_path / "queue.jsonl"
    args = build_parser().parse_args(["--post-interval", "0"])
    with pytest.raises(KeyboardInterrupt):
        capture_frames(Port(), args, BoundedJsonlLog(path), Backend())
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len([row for row in rows if row["event"] == "usb_cycle"]) == 40
    assert any(row.get("status") == "queue_full" for row in rows)
    assert any(row.get("status") == "connection_closed" for row in rows)
    assert all(row["payload"]["bridge_capture_id"] == row["capture_id"]
               for row in rows if row["event"] == "usb_cycle")


def test_server_logs_stationary_and_failed_cycles(packet, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "uwb_calibration_enabled", True)
    from app.main import app
    from app.routers import uwb
    rows = []
    monkeypatch.setattr(uwb, "record_observation", lambda row: rows.append(copy.deepcopy(row)) or True)
    monkeypatch.setattr(uwb, "filter_location", lambda worker_id, x, y, previous: previous)
    with TestClient(app) as client:
        for sequence, cycle in ((255, 255), (0, 256)):
            packet.update(sequence=sequence, cycle_id=cycle, measured_uptime_us=cycle*300000, measurement_id=packet["session_id"] + f":{cycle}")
            for item in packet["observations"]:
                item["measured_uptime_us"] = cycle*300000
            response = client.post("/api/uwb/distances", json=packet)
            assert response.status_code == 200, response.text
            assert response.json()["location"]["changed"] is False
            assert response.json()["observation"]["measurement_id"] == packet["measurement_id"]
        packet.update(measurements=[], cycle_id=257, measured_uptime_us=257*300000, measurement_id=packet["session_id"] + ":257")
        assert client.post("/api/uwb/distances", json=packet).status_code == 422
    assert len(rows) == 3
    assert all(row["server_received_at"] for row in rows)
    assert all(row["candidate_position"] is not None for row in rows[:2])
    assert rows[2]["status"] == "failed" and rows[2]["candidate_position"] is None
    assert rows[0]["processed_measurements"][0]["server_calibration_offset_m"] == 0.48


def test_legacy_client_is_accepted_with_explicit_missing_diagnostics(packet):
    legacy = {key: packet[key] for key in ("worker_id", "helmet_id", "device_id", "uwb_tag_id", "measurements")}
    parsed = UwbDistancesIn.model_validate(legacy)
    assert parsed.session_id is None and parsed.measured_at is None
    assert parsed.measurements[0].diagnostics.status == "missing"


def test_usb_wifi_duplicate_does_not_solve_position_twice(packet, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "uwb_calibration_enabled", True)
    from app.main import app
    from app.routers import uwb
    from uwb_live_bridge import raw_measurements
    calls, rows = [], []
    def solve(anchors, measurements):
        calls.append(copy.deepcopy(measurements))
        return 2.0, 2.0, 1.0
    monkeypatch.setattr(uwb, "solve_position", solve)
    monkeypatch.setattr(uwb, "record_observation", lambda row: rows.append(copy.deepcopy(row)) or True)
    frame = parse_tag_line(json.dumps(packet))
    usb = build_cycle_payload(frame, raw_measurements(frame), "2026-10-15T00:00:00Z")
    with TestClient(app) as client:
        assert client.post("/api/uwb/distances", json={**packet, "transport": "wifi"}).status_code == 200
        duplicate = client.post("/api/uwb/distances", json=usb)
        assert duplicate.status_code == 200
        assert duplicate.json()["observation"]["accepted"] is False
        assert duplicate.json()["observation"]["reason"] == "duplicate_measurement"
    assert len(calls) == 1 and len(rows) == 2
    assert rows[1]["status"] == "ignored"
    assert calls[0][0]["distance_m"] == pytest.approx(4.98)
