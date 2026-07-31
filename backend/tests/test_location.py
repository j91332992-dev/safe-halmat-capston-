from app.services.location_service import solve_position


def test_solve_position_four_anchors():
    anchors = [
        {"anchor_id": "a1", "x": 0, "y": 0},
        {"anchor_id": "a2", "x": 12, "y": 0},
        {"anchor_id": "a3", "x": 12, "y": 8},
        {"anchor_id": "a4", "x": 0, "y": 8},
    ]
    expected = (4.0, 3.0)
    measurements = [
        {"anchor_id": a["anchor_id"], "distance_m": ((expected[0] - a["x"]) ** 2 + (expected[1] - a["y"]) ** 2) ** 0.5, "quality": 1}
        for a in anchors
    ]
    x, y, confidence = solve_position(anchors, measurements)
    assert abs(x - expected[0]) < 0.01
    assert abs(y - expected[1]) < 0.01
    assert confidence > 0.99

