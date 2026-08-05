import json
from functools import lru_cache
from pathlib import Path


CALIBRATION_FILE = Path(__file__).resolve().parents[3] / "uwb_calibration.json"


@lru_cache(maxsize=1)
def calibration_offsets() -> dict[str, float]:
    """프로젝트 공통 UWB 앵커 보정값을 읽습니다."""
    if not CALIBRATION_FILE.exists():
        return {}
    data = json.loads(CALIBRATION_FILE.read_text(encoding="utf-8"))
    return {
        anchor_id: float(offset)
        for anchor_id, offset in data.get("offset_m", {}).items()
    }


def measurements_to_dict(measurements, apply_calibration: bool = False) -> list[dict]:
    offsets = calibration_offsets() if apply_calibration else {}
    return [
        {
            "anchor_id": item.anchor_id,
            "distance_m": round(max(0.05, item.distance_m + offsets.get(item.anchor_id, 0.0)), 3),
            "quality": item.quality,
        }
        for item in measurements
    ]