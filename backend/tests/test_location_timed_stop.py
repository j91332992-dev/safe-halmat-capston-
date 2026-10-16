import pytest
from app.services import location_filter_service as f

@pytest.fixture(autouse=True)
def reset():
    f.reset_location_filter()
    yield
    f.reset_location_filter()

@pytest.mark.parametrize("speed", [.15, .5, 1.0])
def test_constant_motion_never_false_stops(speed):
    previous=None; began=False
    for i in range(101):
        previous=f.filter_location("w", i*.1*speed, 0, previous, now=i*.1)
        moving=f._states["w"].moving
        if began: assert moving
        began |= moving
    assert began

def test_stationary_noise_stays_fixed_under_30cm():
    for i in range(50):
        p=f.filter_location("w", .02 if i%2 else -.02, 0, (0,0), now=i*.1)
        assert p == (0,0)

def test_stops_after_walking_then_settling():
    previous=None
    for i in range(61):
        previous=f.filter_location("w", min(i,40)*.05,0,previous,now=i*.1)
    assert not f._states["w"].moving

def test_gap_alone_does_not_prove_stationary():
    previous=None
    for i in range(30):previous=f.filter_location("w",i*.05,0,previous,now=i*.1)
    f.filter_location("w",1.45,0,previous,now=20)
    assert f._states["w"].moving
