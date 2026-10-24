import math

import pytest

from app.config import Settings
from app.services.location_service import solve_position
from app.services.position_jump_guard import PositionJumpGuard
from app.services.uwb_distance_filter import DistanceFilter
from test_uwb_signal_quality import packet, diagnostic


def config(**kwargs):
    return Settings(_env_file=None, **kwargs)


def test_bad_signal_is_downweighted_without_losing_geometry(tmp_path):
    cfg = config(uwb_quality_mode='weighted', uwb_filter_state_path=str(tmp_path/'state.db'))
    processor = DistanceFilter(cfg, offsets={})
    bad = processor.process(packet(0, diag=diagnostic(15,12)), now=100)
    row = bad['measurements'][0]
    assert row['quality'] == pytest.approx(.15)
    assert bad['quality_summary']['excluded_anchor_ids'] == []
    assert row['signal_quality']['applied_action'] == 'downweight'
    restored = processor.process(packet(1), now=100.3)['measurements'][0]
    assert restored['quality'] == pytest.approx(.25)
    assert restored['signal_quality']['weight_recovery_limited']


def test_unknown_signal_is_retained_at_low_weight(tmp_path):
    processor = DistanceFilter(config(uwb_quality_mode='weighted',
        uwb_filter_state_path=str(tmp_path/'state.db')), offsets={})
    row = processor.process(packet(0, diag={'status':'missing'}), now=100)['measurements'][0]
    assert row['quality'] == pytest.approx(.2)


def test_weighting_reduces_effect_of_one_biased_range():
    anchors = [dict(anchor_id=str(i), x=x, y=y) for i,(x,y) in enumerate([(0,0),(6,0),(6,5),(0,5)])]
    measurements = [dict(anchor_id=a['anchor_id'], distance_m=math.hypot(2-a['x'],2-a['y']),quality=.95) for a in anchors]
    measurements[0]['distance_m'] += .8
    before = solve_position(anchors, measurements)
    measurements[0]['quality'] = .15
    after = solve_position(anchors, measurements)
    assert math.hypot(after[0]-2,after[1]-2) < math.hypot(before[0]-2,before[1]-2)


def acquired_guard():
    guard = PositionJumpGuard(config())
    for i in range(4):
        result = guard.check(packet(i),2,2,now=100+i*.3)
    assert result['accepted']
    return guard


def test_isolated_jump_is_not_applied_and_next_normal_sample_recovers():
    guard = acquired_guard()
    spike = guard.check(packet(4),2.87,2,now=101.2)
    assert not spike['applied'] and spike['reason']=='jump_pending'
    normal = guard.check(packet(5),2.05,2,now=101.5)
    assert normal['accepted'] and normal['reason']=='continuous_motion'


def test_consistent_new_position_can_reacquire_without_permanent_freeze():
    guard = acquired_guard()
    assert not guard.check(packet(4),3.2,2,now=101.2)['applied']
    assert not guard.check(packet(5),3.22,2,now=101.5)['applied']
    recovered = guard.check(packet(6),3.24,2,now=101.8)
    assert recovered['accepted'] and recovered['reason']=='jump_reconfirmed'


def test_alternating_far_candidates_never_confirm():
    guard = acquired_guard()
    for i,x in enumerate([4,0,4,0,4,0],start=4):
        assert not guard.check(packet(i),x,2,now=100+i*.3)['applied']


def test_normal_continuous_walking_is_not_throttled():
    guard = acquired_guard()
    for i in range(4,20):
        result = guard.check(packet(i),2+(i-3)*.25,2,now=100+i*.3)
        assert result['accepted'] and result['reason']=='continuous_motion'


def test_long_gap_requires_reconfirmation_and_state_is_bounded():
    guard = acquired_guard()
    result = guard.check(packet(20),2,2,now=106)
    assert not result['applied'] and result['reason']=='initial_position_pending'


def test_duplicate_clock_cannot_confirm_a_jump():
    guard = acquired_guard()
    first = guard.check(packet(4),3.2,2,now=101.2)
    repeated = guard.check(packet(4),3.2,2,now=101.3)
    assert not first['applied'] and not repeated['applied']
    assert repeated['reason']=='non_increasing_clock'


def test_api_rejects_spike_before_existing_motion_filter(monkeypatch):
    import copy
    from fastapi.testclient import TestClient
    from app.main import app
    from app.config import settings
    from app.routers import uwb
    from test_location_speed_api import packet as api_packet
    monkeypatch.setattr(settings, 'uwb_jump_mode', 'enforce')
    original = DistanceFilter.process
    monkeypatch.setattr(DistanceFilter, 'process', lambda self,p: original(self,p,now=1000+p.measured_uptime_us/1e6))
    observations = []
    monkeypatch.setattr(uwb, 'record_observation', lambda row: observations.append(copy.deepcopy(row)) or True)
    positions = iter([(2,2)]*4+[(2.87,2),(2.05,2)])
    monkeypatch.setattr(uwb, 'solve_position', lambda *args: (*next(positions), .9))
    with TestClient(app) as client:
        for i in range(4):
            client.post('/api/uwb/distances', json=api_packet(i))
        spike = client.post('/api/uwb/distances', json=api_packet(4)).json()
        assert spike['observation']['position_check']['reason']=='jump_pending'
        assert not spike['observation']['pipeline']['position_applied']
        assert not spike['location']['changed']
        recovered = client.post('/api/uwb/distances', json=api_packet(5)).json()
        assert recovered['observation']['pipeline']['position_applied']
        assert observations[-2]['position_jump']['distance_m'] == pytest.approx(.87)
