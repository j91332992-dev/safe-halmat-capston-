import math

import pytest

from app.config import Settings
from app.schemas.api import UwbDistancesIn
from app.services.location_speed_service import LocationSpeedGuard


def packet(cycle, t, session="boot-a", **extra):
    data = dict(
        worker_id="worker-001", helmet_id="helmet-001", device_id="helmet-001-uwb", uwb_tag_id="tag-001",
        session_id=session, measurement_id=f"{session}:{cycle}", cycle_id=cycle, sequence=cycle % 256,
        measured_uptime_us=round(t*1e6), measurements=[])
    data.update(extra)
    return UwbDistancesIn.model_validate(data)


@pytest.fixture
def guard():
    return LocationSpeedGuard(Settings(uwb_speed_mode="enforce"))


def acquire(guard, x=0, y=0):
    results = [guard.check(packet(i, i*.3), x, y, now=100+i*.3) for i in range(3)]
    assert [r["accepted"] for r in results] == [False, False, True]
    return results[-1]


def test_initial_confirmation_and_small_continuous_walk(guard):
    assert acquire(guard)["reset_smoothing"]
    for i in range(3, 30):
        result = guard.check(packet(i, i*.3), (i-2)*.3, 0, now=100+i*.3)
        assert result["accepted"]
        assert result["distance_m"] == pytest.approx(.3)
        assert result["allowed_distance_m"] == pytest.approx(1.9)


def test_stationary_noise_jump_and_return(guard):
    acquire(guard)
    for i in range(3, 7):
        assert guard.check(packet(i, i*.3), (-1)**i*.1, .1, 100+i*.3)["accepted"]
    jump = guard.check(packet(7, 2.1), 100, 0, 102.1)
    assert not jump["accepted"] and not jump["applied"] and jump["reason"] == "speed_exceeded"
    returned = guard.check(packet(8, 2.4), .1, .1, 102.4)
    assert returned["accepted"] and returned["consecutive_rejections"] == 0
    assert returned["reference"]["x"] != 100


def test_observation_logs_rejection_but_keeps_existing_flow(guard):
    guard.config.uwb_speed_mode = "observe"
    acquire(guard)
    bad = guard.check(packet(3, .9), 100, 0, 100.9)
    assert not bad["accepted"] and bad["applied"] and not bad["reset_smoothing"]
    result = guard.check(packet(4, 1.2), 0, 0, 101.2)
    assert result["accepted"] and result["reference"]["x"] == 0


def test_device_intervals_not_network_arrival_intervals(guard):
    acquire(guard)
    # One second of device time: a burst arriving after 0.1 server seconds is valid.
    result = guard.check(packet(3, 1.6), 2.5, 0, 100.7)
    assert result["accepted"] and result["dt_seconds"] == pytest.approx(1)
    # Four seconds of network delay must not give a .3 second measurement a huge radius.
    result = guard.check(packet(4, 1.9), 8, 0, 104.7)
    assert not result["accepted"] and result["allowed_distance_m"] == pytest.approx(1.9)


def test_duplicate_reverse_and_abnormal_times(guard):
    acquire(guard)
    assert guard.check(packet(2, .6), 0, 0, 100.7)["reason"] == "duplicate_measurement"
    assert guard.check(packet(1, .3, measurement_id="other"), 0, 0, 100.8)["reason"] == "out_of_order_cycle"
    assert guard.check(packet(3, .5), 0, 0, 100.9)["reason"] == "non_increasing_or_short_dt"
    assert guard.check(packet(4, .601), 0, 0, 101)["reason"] == "non_increasing_or_short_dt"
    assert guard.check(packet(5, .9), 0, 0, 101.1)["accepted"]


def test_reboot_tag_change_and_server_restart(guard):
    acquire(guard)
    for i in range(3):
        out = guard.check(packet(i, i*.3, session="boot-b"), 100, 0, 101+i*.3)
        assert out["accepted"] == (i == 2)
    assert out["reset_smoothing"]
    assert guard.check(packet(3, .9), 0, 0, 102)["reason"] == "retired_session"
    changed = guard.check(packet(0, 0, session="new-tag", uwb_tag_id="tag-002"), -100, 0, 102.3)
    assert not changed["accepted"] and changed["distance_m"] is None
    guard.reset()
    assert not guard.check(packet(5, 1.5), 0, 0, 103)["accepted"]


@pytest.mark.parametrize("device_gap,server_gap", [(11, 11), (.3, 11)])
def test_disconnect_requires_confirmation(guard, device_gap, server_gap):
    acquire(guard)
    out = guard.check(packet(3, .6+device_gap), 100, 0, 100.6+server_gap)
    assert out["reason"] == "long_gap_acquisition" and not out["accepted"]
    for i in (1, 2):
        out = guard.check(packet(3+i, .6+device_gap+i*.3), 100, 0, 100.6+server_gap+i*.3)
    assert out["accepted"] and out["reset_smoothing"]


def test_consistent_rejections_reacquire_but_not_immediately(guard):
    acquire(guard)
    results = [guard.check(packet(i, i*.3), 100, 0, 100+i*.3) for i in range(3, 11)]
    assert not any(r["accepted"] for r in results[:-1])
    assert results[-1]["accepted"] and results[-1]["reason"] == "reacquired_after_rejections"


def test_alternating_outliers_never_make_confirmed_track(guard):
    acquire(guard)
    for i in range(3, 48):
        result = guard.check(packet(i, i*.3), 100*(-1)**i, 0, 100+i*.3)
        assert not result["accepted"]


def test_unknown_clock_legacy_and_nonfinite(guard):
    p = packet(0, 0).model_copy(update={"session_id": None, "measured_uptime_us": None})
    assert not guard.check(p, 1, 1, 100)["applied"]
    guard.config.uwb_speed_mode = "observe"
    assert guard.check(p, 1, 1, 100)["applied"]
    assert not guard.check(packet(0, 0), math.nan, 1, 100)["applied"]


def test_runtime_mode_transition_requires_new_acquisition(guard):
    guard.config.uwb_speed_mode = "observe"
    acquire(guard)
    guard.config.uwb_speed_mode = "enforce"
    result = guard.check(packet(3, .9), 100, 0, 100.9)
    assert not result["applied"] and result["reason"] == "policy_changed"


def test_memory_expiry_and_capacity(guard):
    guard.config.uwb_filter_max_tags = 2
    for i in range(3):
        guard.check(packet(0, 0, worker_id=f"worker-{i}"), 0, 0, 100+i)
    assert len(guard.states) == 2
    guard.check(packet(0, 0), 0, 0, 4000)
    assert len(guard.states) == 1


def test_bad_initial_reference_is_not_permanent(guard):
    acquire(guard, x=100)
    results = [guard.check(packet(i, i*.3), 0, 0, 100+i*.3) for i in range(3, 11)]
    assert not any(r["accepted"] for r in results[:-1])
    assert results[-1]["accepted"] and results[-1]["reset_smoothing"]


def test_acquisition_allows_a_walking_track(guard):
    results = [guard.check(packet(i, i*.3), i*.45, 0, 100+i*.3) for i in range(6)]
    assert not results[0]["accepted"] and not results[1]["accepted"]
    assert all(r["accepted"] for r in results[2:])


def test_valid_twenty_millisecond_boundary_and_sequence_wrap(guard):
    acquire(guard)
    for i in range(3, 23):
        t = .6+(i-2)*.02
        assert guard.check(packet(i, t), 0, 0, 100+t)["accepted"]
    assert guard.check(packet(255, 1.3), 0, 0, 101.3)["accepted"]
    assert guard.check(packet(256, 1.6), 0, 0, 101.6)["accepted"]
