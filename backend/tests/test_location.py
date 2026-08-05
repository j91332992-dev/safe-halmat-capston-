from app.services.location_service import solve_position
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
