"""Historical task-1 offline comparison only; never used for transport."""
from pathlib import Path
import json
from collections import defaultdict, deque
from statistics import median
import time
from uwb_live_bridge import TagFrame, ANCHOR_ID_MAP

DEFAULT_CALIBRATION_FILE = Path(__file__).resolve().parents[1] / "uwb_calibration.json"

def load_calibration(path: Path, disabled: bool = False) -> dict[str, float]:
    if disabled:
        return {anchor_id: 0.0 for anchor_id in ANCHOR_ID_MAP.values()}
    data = json.loads(path.read_text(encoding="utf-8"))
    offsets = data.get("offset_m", data)
    return {
        anchor_id: float(offsets.get(anchor_id, 0.0))
        for anchor_id in ANCHOR_ID_MAP.values()
    }


class DistanceProcessor:
    """최근 거리 중앙값과 앵커별 보정을 적용합니다."""

    def __init__(self, calibration: dict[str, float], history_size: int = 5, anchor_hold_seconds: float = 2.5):
        self.calibration = calibration
        self.history = defaultdict(lambda: deque(maxlen=history_size))
        self.last_seen: dict[str, float] = {}
        self.anchor_hold_seconds = anchor_hold_seconds
        self.sources = {}
        self.sessions = {}

    def process(self, frame: TagFrame) -> list[dict]:
        now = time.monotonic()
        session = frame.payload.get("session_id") if frame.payload else None
        if frame.tag_id in self.sessions and self.sessions[frame.tag_id] != session:
            # Do not combine samples or held diagnostics across a reboot.
            for key in list(self.last_seen):
                if key[0] == frame.tag_id:
                    self.history.pop(key, None)
                    self.last_seen.pop(key, None)
                    self.sources.pop(key, None)
        self.sessions[frame.tag_id] = session
        observations = {item["anchor_id"]: item for item in (frame.payload or {}).get("observations", [])}
        current: dict[str, int] = {}
        for raw_cm, anchor_number in zip(frame.ranges_cm, frame.anchor_numbers):
            anchor_id = ANCHOR_ID_MAP.get(anchor_number)
            if anchor_id is None or raw_cm <= 0:
                continue
            current[anchor_id] = raw_cm
            key = (frame.tag_id, anchor_id)
            self.history[key].append(raw_cm)
            self.last_seen[key] = now
            self.sources[key] = (observations.get(anchor_id), (frame.payload or {}).get("measurement_id"))

        measurements = []
        recent_anchor_ids = {
            anchor_id for (tag_id, anchor_id), seen_at in self.last_seen.items()
            if tag_id == frame.tag_id and now - seen_at <= self.anchor_hold_seconds
        }
        for anchor_id in sorted(recent_anchor_ids):
            key = (frame.tag_id, anchor_id)
            samples = self.history[key]
            smoothed_cm = float(median(samples))
            distance_m = max(0.05, smoothed_cm / 100.0 + self.calibration.get(anchor_id, 0.0))
            spread_cm = max(samples) - min(samples) if len(samples) > 1 else 0
            age = now - self.last_seen[key]
            held_penalty = 0.15 if anchor_id not in current else 0.0
            age_penalty = held_penalty + min(
                0.20, age / max(0.001, self.anchor_hold_seconds) * 0.20
            )
            quality = max(0.40, min(0.99, 0.98 - spread_cm / 250.0 - age_penalty))
            source, source_id = self.sources[key]
            measurements.append(
                {
                    "anchor_id": anchor_id,
                    "distance_m": round(distance_m, 3),
                    "quality": round(quality, 2),
                    "raw_distance_m": source.get("raw_distance_m") if source else current.get(anchor_id, samples[-1]) / 100.0,
                    "median_distance_m": smoothed_cm / 100.0,
                    "calibration_offset_m": self.calibration.get(anchor_id, 0.0),
                    "held": anchor_id not in current,
                    "source_measurement_id": source_id,
                    "diagnostics": source.get("diagnostics", {"status": "missing", "reason": "legacy_client"}) if source else {"status": "missing", "reason": "legacy_client"},
                }
            )
        return measurements
