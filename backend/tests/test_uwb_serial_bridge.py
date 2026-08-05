from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from uwb_live_bridge import DistanceProcessor, parse_tag_line


def test_parse_full_tag_frame():
    frame = parse_tag_line(
        "T0,mask:F,seq:21,beacon:15,range:(454,524,572,486),ancid:(0,1,2,3)"
    )
    assert frame is not None
    assert frame.tag_id == 0
    assert frame.mask == 0xF
    assert frame.ranges_cm == (454, 524, 572, 486)
    assert frame.anchor_numbers == (0, 1, 2, 3)


def test_parse_ignores_boot_log():
    assert parse_tag_line("PLL is locked..") is None


def test_calibration_places_center_sample_near_expected_distance():
    frame = parse_tag_line(
        "T0,mask:F,seq:1,beacon:1,range:(454,513,570,469),ancid:(0,1,2,3)"
    )
    assert frame is not None
    processor = DistanceProcessor(
        {
            "anchor-001": 0.48,
            "anchor-002": -0.11,
            "anchor-003": -0.69,
            "anchor-004": 0.33,
        },
        history_size=1,
    )
    measurements = processor.process(frame)
    distances = {item["anchor_id"]: item["distance_m"] for item in measurements}
    assert distances == {
        "anchor-001": 5.02,
        "anchor-002": 5.02,
        "anchor-003": 5.01,
        "anchor-004": 5.02,
    }


def test_partial_frame_keeps_only_valid_anchors():
    frame = parse_tag_line(
        "T0,mask:D,seq:2,beacon:2,range:(450,0,560,470),ancid:(0,-1,2,3)"
    )
    assert frame is not None
    measurements = DistanceProcessor({}, history_size=1).process(frame)
    assert [item["anchor_id"] for item in measurements] == [
        "anchor-001",
        "anchor-003",
        "anchor-004",
    ]

def test_parse_anchor_receiver_frame():
    frame = parse_tag_line(
        "T0,mask:F,seq:21,fail:0,range:(454,524,572,486,0,0,0,0),ancid:(0,1,2,3,-1,-1,-1,-1)"
    )
    assert frame is not None
    assert frame.beacon == -1
    processor = DistanceProcessor({}, history_size=1)
    measurements = processor.process(frame)
    assert [item["anchor_id"] for item in measurements] == [
        "anchor-001",
        "anchor-002",
        "anchor-003",
        "anchor-004",
    ]

def test_backend_applies_raw_distance_calibration():
    from app.schemas.api import DistanceMeasurement
    from app.services.uwb_service import measurements_to_dict

    raw = [
        DistanceMeasurement(anchor_id="anchor-001", distance_m=4.54, quality=0.9),
        DistanceMeasurement(anchor_id="anchor-002", distance_m=5.13, quality=0.9),
        DistanceMeasurement(anchor_id="anchor-003", distance_m=5.70, quality=0.9),
        DistanceMeasurement(anchor_id="anchor-004", distance_m=4.69, quality=0.9),
    ]
    corrected = measurements_to_dict(raw, apply_calibration=True)
    assert [item["distance_m"] for item in corrected] == [5.02, 5.02, 5.01, 5.02]