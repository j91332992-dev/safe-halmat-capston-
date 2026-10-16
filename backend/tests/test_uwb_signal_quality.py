import json
import sqlite3

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.schemas.api import UwbDiagnostics, UwbDistancesIn
from app.services.uwb_distance_filter import DistanceFilter
from app.services.uwb_quality_service import classify_signal


def diagnostic(gap=3, path=1, rx=-75):
    return dict(status="valid", rx_power_dbm=rx, first_path_power_dbm=rx-gap, power_difference_db=gap,
                peak_minus_first_path_samples=path, clock_offset_ppm=.5, raw={"ipatov_accum_count": 128})


def packet(cycle=0, value=2, diag=None, **extra):
    data = dict(schema_version=2, worker_id="worker-001", helmet_id="helmet-001", device_id="helmet-001-uwb",
                uwb_tag_id="tag-001", session_id="boot-a", cycle_id=cycle, sequence=cycle % 256,
                measurement_id=f"boot-a:{cycle}", measured_uptime_us=cycle*300000, distances_calibrated=False,
                observations=[dict(anchor_id="anchor-001", status="valid", raw_distance_m=value,
                                   diagnostics=diag if diag is not None else diagnostic())],
                measurements=[dict(anchor_id="anchor-001", distance_m=value, quality=.95)])
    data.update(extra)
    return UwbDistancesIn.model_validate(data)


@pytest.fixture
def processor(tmp_path):
    return DistanceFilter(Settings(uwb_quality_mode="enforce", uwb_filter_state_path=str(tmp_path/"state.db")), offsets={})


def run(processor, cycle, value=2, diag=None, **extra):
    return processor.process(packet(cycle, value, diag, **extra), 100+cycle*.3)


@pytest.mark.parametrize("data,category,nlos,action", [
    (diagnostic(), "nominal", False, "use"),
    (diagnostic(rx=-100), "suspect", False, "downweight"),
    (diagnostic(gap=15, path=1), "suspect", True, "downweight"),
    (diagnostic(gap=3, path=12), "suspect", True, "downweight"),
    (diagnostic(gap=15, path=12), "nlos_suspected", True, "exclude"),
    ({"status": "missing"}, "unknown", None, "downweight"),
    ({"status": "invalid", "reason": "zero_accum_count", "raw": {"ipatov_accum_count": 0}}, "unknown", None, "downweight")])
def test_multi_metric_classification(data, category, nlos, action):
    result = classify_signal(UwbDiagnostics.model_validate(data), Settings())
    assert result["classification"] == category and result["suspected_nlos"] is nlos
    assert result["would_action"] == action and result["thresholds"]


def test_inconsistent_power_is_invalid_not_nominal():
    data = diagnostic()
    data["power_difference_db"] = 9
    result = classify_signal(UwbDiagnostics.model_validate(data), Settings())
    assert result["classification"] == "unknown" and result["diagnostic_validity"] == "invalid"


def test_observation_does_not_change_distances_history_or_client_weights(processor):
    processor.settings.uwb_quality_mode = "observe"
    other = DistanceFilter(processor.settings.model_copy(update={"uwb_filter_state_path": processor.settings.uwb_filter_state_path+".other"}), offsets={})
    for i, value in enumerate([2, 2, 9, 2, 2]):
        a = run(processor, i, value, diagnostic(gap=15, path=12))
        b = run(other, i, value, diagnostic())
        for field in ("distance_m", "quality", "sample_count", "sample_ages_seconds"):
            assert a["measurements"][0][field] == b["measurements"][0][field]
        assert a["measurements"][0]["quality"] == .95
        assert a["anchor_processing"][0]["signal_quality"]["applied_action"] == "observe"


def test_exclusion_clears_history_and_never_holds_old_value(processor):
    assert run(processor, 0)["measurements"]
    bad = run(processor, 1, 8, diagnostic(15, 12))
    assert bad["measurements"] == []
    assert bad["anchor_processing"][0]["calibrated_distance_m"] is None
    assert bad["quality_summary"]["excluded_anchor_ids"] == ["anchor-001"]
    with sqlite3.connect(processor.settings.uwb_filter_state_path) as db:
        state = json.loads(db.execute("SELECT data FROM distance_state").fetchone()[0])
        assert state["histories"] == {}
    assert run(processor, 2, 9, diagnostic(8, 5))["measurements"] == []
    assert run(processor, 3, 2.1)["measurements"] == []
    duplicate = processor.process(packet(3, 2.1, transport="usb"), 101)
    assert duplicate["reason"] == "duplicate_measurement"
    assert run(processor, 4, 2.2)["measurements"] == []
    recovered = run(processor, 5, 2.3)
    assert recovered["measurements"][0]["distance_m"] == 2.3
    assert recovered["measurements"][0]["sample_count"] == 1


def test_suspect_weight_and_class_transition_prevent_biased_history(processor):
    run(processor, 0)
    out = run(processor, 1, 9, diagnostic(8, 5))
    assert out["measurements"][0]["distance_m"] == 9
    assert out["measurements"][0]["sample_count"] == 1
    assert out["measurements"][0]["quality"] == .35
    assert run(processor, 2, 8, diagnostic(8, 5))["measurements"][0]["distance_m"] == 8.5
    assert run(processor, 3, 2.1)["measurements"] == []
    assert run(processor, 4, 2.2)["measurements"] == []
    out = run(processor, 5, 2.3)
    assert out["measurements"][0]["distance_m"] == 2.3
    assert out["measurements"][0]["sample_count"] == 1


def test_missing_invalid_and_fixed_quality_are_not_real_signal_quality(processor):
    p = packet(0, diag={"status": "missing"})
    p.measurements[0].quality = 1
    result = processor.process(p, 100)
    assert result["measurements"][0]["quality"] == .2
    assert result["measurements"][0]["signal_quality"]["classification"] == "unknown"
    assert not result["measurements"][0]["signal_quality"]["client_quality_is_uwb_diagnostic"]
    processor.settings.uwb_quality_unknown_policy = "exclude"
    assert run(processor, 1, diag={"status": "invalid"})["measurements"] == []


def test_dropout_interrupts_recovery(processor):
    run(processor, 0, 9, diagnostic(15, 12))
    assert run(processor, 1)["measurements"] == []
    run(processor, 2, observations=[dict(anchor_id="anchor-001", status="missing")], measurements=[])
    assert run(processor, 3)["measurements"] == []
    assert run(processor, 4)["measurements"] == []
    assert run(processor, 5)["measurements"][0]["sample_count"] == 1


def test_policy_change_and_reboot_reset_bias(processor):
    processor.settings.uwb_quality_mode = "observe"
    run(processor, 0, 9, diagnostic(15, 12))
    processor.settings.uwb_quality_mode = "enforce"
    assert run(processor, 1, 2)["measurements"][0]["distance_m"] == 2
    run(processor, 2, 9, diagnostic(15, 12))
    reboot = packet(0, session_id="boot-b", measurement_id="boot-b:0")
    out = processor.process(reboot, 101)
    assert out["measurements"][0]["distance_m"] == 2


def test_thresholds_configurable_and_ordered():
    data = UwbDiagnostics.model_validate(diagnostic(15, 12))
    cfg = Settings(uwb_quality_gap_bad_db=20, uwb_quality_path_bad_samples=20)
    assert classify_signal(data, cfg)["would_action"] == "downweight"
    with pytest.raises(ValidationError):
        Settings(uwb_quality_gap_bad_db=4)


def test_new_operating_defaults_keep_raw_distance_and_ignore_signal_actions(processor):
    from app.config import Settings
    defaults = Settings(_env_file=None)
    assert defaults.uwb_calibration_enabled is False and defaults.uwb_quality_mode == "observe"
    processor.settings.uwb_quality_mode = defaults.uwb_quality_mode
    processor.settings.uwb_calibration_enabled = defaults.uwb_calibration_enabled
    processor.offsets = {"anchor-001": .48}
    for i, value in enumerate((2, 2, 8, 2, 2)):
        result = run(processor, i, value, diagnostic(15, 12))
        m = result["measurements"][0]
        assert m["distance_m"] == 2 and m["quality"] == .95
        assert m["server_calibration_offset_m"] == 0
        assert m["signal_quality"]["would_action"] == "exclude"
        assert m["signal_quality"]["applied_action"] == "observe"
