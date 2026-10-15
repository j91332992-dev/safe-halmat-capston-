from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from app.config import Settings
from app.schemas.api import UwbDistancesIn
from app.services.uwb_distance_filter import DistanceFilter


def packet(cycle=0, value=2, session="boot-a", **extra):
    data = dict(worker_id="worker-001", helmet_id="helmet-001", device_id="helmet-001-uwb",
                uwb_tag_id="tag-001", schema_version=2, session_id=session,
                measurement_id=f"{session}:{cycle}", cycle_id=cycle, sequence=cycle % 256,
                measured_uptime_us=cycle*300000, distances_calibrated=False,
                measurements=[dict(anchor_id="anchor-001", distance_m=value)])
    data.update(extra)
    return UwbDistancesIn.model_validate(data)


@pytest.fixture
def processor(tmp_path):
    return DistanceFilter(Settings(uwb_filter_state_path=str(tmp_path / "state.db")), offsets={})


def distance(result):
    return result["measurements"][0]["distance_m"]


def test_spike_warmup_and_sample_counts(processor):
    outputs = [processor.process(packet(i, v), now=100+i*.3) for i, v in enumerate([2, 2, 2, 8, 2])]
    assert [distance(r) for r in outputs] == [2]*5
    assert [r["measurements"][0]["sample_count"] for r in outputs] == [1, 2, 3, 4, 5]
    assert outputs[0]["measurements"][0]["reason"] == "warmup_partial_window"
    assert outputs[-1]["measurements"][0]["sample_ages_seconds"] == [1.2, .9, .6, .3, 0]


@pytest.mark.parametrize("window,lag", [(3, 1), (5, 2)])
def test_step_and_ramp_delay(processor, window, lag):
    processor.settings.uwb_median_window = window
    values = [2]*5 + [4]*5
    outputs = [distance(processor.process(packet(i, v), 100+i*.3)) for i, v in enumerate(values)]
    assert outputs[5:5+lag] == [2]*lag
    assert outputs[5+lag] == 4
    processor.settings.uwb_filter_state_path += ".ramp"
    outputs = [distance(processor.process(packet(i, i+1), 100+i*.3)) for i in range(10)]
    assert outputs[-1] == 10-lag


def test_disabled_still_deduplicates(processor):
    processor.settings.uwb_median_enabled = False
    for i, v in enumerate([2, 2, 8]):
        assert distance(processor.process(packet(i, v), 100+i*.3)) == v
    assert processor.process(packet(2, 8), 100.7)["reason"] == "duplicate_measurement"


def test_multitag_site_and_anchor_isolation(processor):
    assert distance(processor.process(packet(value=2), 100)) == 2
    assert distance(processor.process(packet(value=8, uwb_tag_id="tag-002"), 100)) == 8
    assert distance(processor.process(packet(value=6, site_id="site-002"), 100)) == 6
    p = packet(1, 4)
    p.measurements.append(p.measurements[0].model_copy(update={"anchor_id": "anchor-002", "distance_m": 9}))
    out = processor.process(p, 100.3)
    assert [m["distance_m"] for m in out["measurements"]] == [3, 9]


def test_missing_return_expiry_and_no_hold(processor):
    processor.process(packet(), 100)
    out = processor.process(packet(1, measurements=[], observations=[dict(anchor_id="anchor-001", status="missing")]), 100.3)
    assert out["measurements"] == [] and out["anchor_processing"][0]["reason"] == "missing"
    out = processor.process(packet(2, 4), 100.6)
    assert distance(out) == 3 and out["measurements"][0]["sample_count"] == 2
    out = processor.process(packet(14, 8), 104.2)
    assert distance(out) == 8 and out["measurements"][0]["sample_count"] == 1
    out = processor.process(packet(15, measurements=[dict(anchor_id="anchor-001", distance_m=8, held=True)]), 104.5)
    assert out["measurements"] == []
    assert out["anchor_processing"][0]["reason"] == "client_held_rejected"


def test_two_transports_duplicate_and_replay_order(processor):
    processor.process(packet(255, 2, transport="wifi"), 100)
    duplicate = processor.process(packet(255, 2, transport="usb"), 100.01)
    assert duplicate["reason"] == "duplicate_measurement"
    wrapped = processor.process(packet(256, 4), 100.3)
    assert distance(wrapped) == 3 and wrapped["measurements"][0]["sample_count"] == 2
    assert processor.process(packet(254), 100.4)["reason"] == "out_of_order"
    assert processor.process(packet(256, measurement_id="different"), 100.5)["reason"] == "duplicate_cycle"
    assert processor.process(packet(257, measurement_id="boot-a:255"), 100.6)["reason"] == "duplicate_measurement"


def test_reboot_and_retired_session(processor):
    processor.process(packet(255), 100)
    out = processor.process(packet(0, 6, session="boot-b"), 100.3)
    assert distance(out) == 6 and out["measurements"][0]["reason"] == "session_changed"
    assert processor.process(packet(256), 100.6)["reason"] == "retired_session"


def test_long_gap_resets_but_keeps_watermark(processor):
    processor.process(packet(), 100)
    out = processor.process(packet(100, 9), 130)
    assert distance(out) == 9 and out["measurements"][0]["reason"] == "long_gap_reset"
    assert processor.process(packet(), 130.1)["reason"] == "duplicate_measurement"


def test_old_absolute_relative_and_future_frames(processor):
    processor.process(packet(), 100)
    assert processor.process(packet(1), 110)["reason"] == "stale_frame"
    absolute = datetime.fromtimestamp(90, timezone.utc)
    assert processor.process(packet(2, measured_at=absolute), 100)["reason"] == "stale_frame"
    assert processor.process(packet(2, measured_at=datetime.fromtimestamp(110, timezone.utc)), 100)["reason"] == "future_frame"
    # Rejections must not advance cycle or poison the history.
    assert processor.process(packet(1), 100.3)["accepted"]


def test_calibration_once_and_mode_change(processor):
    processor.settings.uwb_calibration_enabled = True
    processor.offsets = {"anchor-001": .48}
    assert distance(processor.process(packet(), 100)) == 2.48
    out = processor.process(packet(1, 2.48, distances_calibrated=True), 100.3)
    assert distance(out) == 2.48
    assert out["measurements"][0]["server_calibration_offset_m"] == 0
    assert out["measurements"][0]["sample_count"] == 1


def test_legacy_no_identity_does_not_fill_window(processor):
    p = packet().model_dump()
    for name in ("session_id", "measurement_id", "cycle_id", "measured_uptime_us"):
        p.pop(name)
    p["schema_version"] = 1
    for i in range(5):
        out = processor.process(UwbDistancesIn.model_validate(p), 100+i*.1)
        assert out["reason"] == "legacy_identity_missing_no_history"
        assert out["measurements"][0]["sample_count"] == 1
    with sqlite3.connect(processor.settings.uwb_filter_state_path) as db:
        assert db.execute("SELECT count(*) FROM distance_state").fetchone()[0] == 0


def test_state_ttl_capacity_and_restart(processor):
    processor.settings.uwb_filter_max_tags = 2
    for i in range(3):
        processor.process(packet(uwb_tag_id=f"tag-{i}"), 100+i)
    with sqlite3.connect(processor.settings.uwb_filter_state_path) as db:
        assert db.execute("SELECT count(*) FROM distance_state").fetchone()[0] == 2
    restarted = DistanceFilter(processor.settings, offsets={})
    assert restarted.process(packet(uwb_tag_id="tag-2"), 103)["reason"] == "duplicate_measurement"
    restarted.process(packet(uwb_tag_id="fresh"), 4000)
    with sqlite3.connect(processor.settings.uwb_filter_state_path) as db:
        assert db.execute("SELECT count(*) FROM distance_state").fetchone()[0] == 1


def test_actual_separate_processes_share_atomic_dedup(processor):
    code = '''import sys,json
sys.path.insert(0,sys.argv[1])
from app.config import Settings
from app.schemas.api import UwbDistancesIn
from app.services.uwb_distance_filter import DistanceFilter
p=UwbDistancesIn.model_validate_json(sys.argv[3])
r=DistanceFilter(Settings(uwb_filter_state_path=sys.argv[2]), offsets={}).process(p,100)
print(json.dumps(r))
'''
    command = [sys.executable, "-c", code, str(Path(__file__).resolve().parents[1]),
               processor.settings.uwb_filter_state_path, packet().model_dump_json()]
    processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
    results = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, stderr
        results.append(json.loads(stdout))
    assert sorted(r["accepted"] for r in results) == [False, True]


def test_raw_precision_and_invalid_diagnostics_do_not_gate_distance(processor):
    p = packet(observations=[dict(anchor_id="anchor-001", status="valid", raw_distance_m=2.004321,
                                 diagnostics=dict(status="invalid", reason="zero_accum_count"))])
    out = processor.process(p, 100)
    assert distance(out) == 2.004321
    assert out["anchor_processing"][0]["diagnostics"]["status"] == "invalid"


def test_unseen_older_firmware_boot_is_rejected(processor):
    current = "0c6ce9319d48-5-" + "a"*32
    old = "0c6ce9319d48-4-" + "b"*32
    processor.process(packet(session=current), 100)
    assert processor.process(packet(session=old), 101)["reason"] == "older_or_conflicting_boot"


def test_even_warmup_and_source_identity(processor):
    processor.process(packet(0, 2), 100)
    assert distance(processor.process(packet(1, 4), 100.3)) == 3
    p = packet(2)
    p.measurements[0].source_measurement_id = "boot-a:0"
    result = processor.process(p, 100.6)
    assert result["measurements"] == []
    assert result["anchor_processing"][0]["reason"] == "source_measurement_mismatch"


def test_invalid_and_expired_anchor_samples(processor):
    bad = packet(observations=[dict(anchor_id="anchor-001", status="invalid", raw_distance_m=-2)])
    out = processor.process(bad, 100)
    assert out["measurements"] == [] and out["anchor_processing"][0]["reason"] == "invalid"
    old = packet(20, observations=[dict(anchor_id="anchor-001", status="valid", raw_distance_m=2, measured_uptime_us=0)])
    out = processor.process(old, 106)
    assert out["measurements"] == []
    assert out["anchor_processing"][0]["reason"] == "stale_or_future_sample"


def test_equal_transports_through_separate_common_states(processor):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from uwb_live_bridge import parse_tag_line, raw_measurements, build_cycle_payload
    data = packet().model_dump(mode="json")
    data.update(tag_hw_id=0, observations=[dict(anchor_id="anchor-001", status="valid", raw_distance_m=2.004)])
    frame = parse_tag_line(json.dumps(data))
    usb = UwbDistancesIn.model_validate(build_cycle_payload(frame, raw_measurements(frame), "2026-10-15T00:00:00Z"))
    wifi = UwbDistancesIn.model_validate({**data, "transport": "wifi"})
    a = processor.process(usb, 100)
    processor.settings.uwb_filter_state_path += ".wifi"
    b = processor.process(wifi, 100)
    assert a == b


def test_disabled_calibration_does_not_load_or_apply_historical_offsets(processor, monkeypatch):
    from app.services import uwb_distance_filter
    processor.offsets = None
    processor.settings.uwb_calibration_enabled = False
    def forbidden():
        pytest.fail("disabled calibration must not read historical offsets")
    monkeypatch.setattr(uwb_distance_filter, "calibration_offsets", forbidden)
    result = processor.process(packet(value=2), 100)
    assert distance(result) == 2
    assert result["measurements"][0]["server_calibration_offset_m"] == 0
    assert result["measurements"][0]["calibration_source"] == "disabled"


def test_disabling_calibration_drops_old_offset_samples(processor):
    processor.settings.uwb_calibration_enabled = True
    processor.offsets = {"anchor-001": .48}
    assert distance(processor.process(packet(), 100)) == 2.48
    processor.settings.uwb_calibration_enabled = False
    result = processor.process(packet(1), 100.3)
    assert distance(result) == 2
    assert result["measurements"][0]["sample_count"] == 1
