from app.services.location_service import solve_position
from app.services.location_filter_service import filter_location, reset_location_filter
from app.site_profile import clamp_position


def test_solve_position_four_anchors():
    anchors = [
        {"anchor_id": "a1", "x": 0, "y": 0},
        {"anchor_id": "a2", "x": 5.8, "y": 0},
        {"anchor_id": "a3", "x": 5.8, "y": 8.2},
        {"anchor_id": "a4", "x": 0, "y": 8.2},
    ]
    expected = (2.2, 3.4)
    measurements = [
        {
            "anchor_id": a["anchor_id"],
            "distance_m": ((expected[0] - a["x"]) ** 2 + (expected[1] - a["y"]) ** 2) ** 0.5,
            "quality": 1,
        }
        for a in anchors
    ]
    x, y, confidence = solve_position(anchors, measurements)
    assert abs(x - expected[0]) < 0.01
    assert abs(y - expected[1]) < 0.01
    assert confidence > 0.99


def test_clamp_position_to_test_site():
    assert clamp_position(-0.1, 9.0) == (0.0, 8.2)
    assert clamp_position(6.0, -1.0) == (5.8, 0.0)


def test_stationary_jitter_is_held_and_real_movement_is_confirmed():
    worker_id = "stationary-filter-test"
    reset_location_filter(worker_id)
    previous = (2.0, 3.0)
    for point in ((2.04, 2.97), (1.94, 3.05), (2.08, 3.02), (1.91, 2.96)):
        assert filter_location(worker_id, *point, previous) == previous

    outputs = [filter_location(worker_id, 2.50, 3.0, previous) for _ in range(5)]
    assert outputs[0] == previous
    assert outputs[1] == previous
    assert outputs[-1][0] > 2.2


def test_small_steps_accumulate_from_last_accepted_position():
    worker_id = "cumulative-movement-filter-test"
    reset_location_filter(worker_id)
    previous = (2.0, 3.0)

    # Each individual sample advances only 10 cm. The comparison must remain
    # against the last accepted position, so cumulative movement is not lost.
    outputs = [
        filter_location(worker_id, x, 3.0, previous)
        for x in (2.10, 2.20, 2.30, 2.40, 2.50, 2.60)
    ]

    assert outputs[:4] == [previous] * 4
    assert outputs[4][0] > previous[0]
    assert outputs[5][0] > outputs[4][0]
