"""Latest live orientation; bounded, transient, no database writes per sample."""
import math
from time import monotonic
from ..database import utcnow

_latest: dict[str, tuple[float, dict]] = {}

def record_orientation(device_id: str, data: dict) -> dict | None:
    values = [data.get(key) for key in ("yaw_deg", "pitch_deg", "roll_deg")]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        return None
    if any(abs(v) > 360 for v in values):
        return None
    now = monotonic()
    previous = _latest.get(device_id)
    if previous and now - previous[0] < .05:
        return None
    result = {"device_id": device_id, "imu_yaw_deg": values[0],
              "imu_pitch_deg": values[1], "imu_roll_deg": values[2],
              "heading_at": utcnow().isoformat() + "Z"}
    _latest[device_id] = (now, result)
    return result

def live_status(device_id: str, status: dict) -> dict:
    sample = _latest.get(device_id)
    if sample and monotonic() - sample[0] < 2:
        status = dict(status)
        status.update({key: value for key, value in sample[1].items() if key.startswith("imu_")})
        status.update(imu="ready", imu_received_at=sample[1]["heading_at"], heading_transport="websocket")
    elif sample:
        # Never replace an expired live direction with an older heartbeat angle.
        status = dict(status)
        status.update(imu="unverified", imu_received_at=sample[1]["heading_at"], heading_transport="websocket")
    return status
