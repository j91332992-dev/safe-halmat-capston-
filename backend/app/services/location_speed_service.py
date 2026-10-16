"""Candidate checks before coordinate smoothing. Single server worker only."""
import math
import time
from threading import Lock

from ..config import settings
from .uwb_distance_filter import SESSION_RE


class LocationSpeedGuard:
    def __init__(self, config):
        self.config = config
        self.states = {}
        self.lock = Lock()

    def reset(self):
        with self.lock:
            self.states.clear()

    def check(self, payload, x, y, now=None):
        now = time.monotonic() if now is None else now
        cfg = self.config
        key = (payload.organization_id, payload.site_id, payload.worker_id)
        with self.lock:
            self.states = {k: v for k, v in self.states.items() if now-v["touched"] <= cfg.uwb_speed_state_ttl_seconds}
            if key not in self.states and len(self.states) >= cfg.uwb_filter_max_tags:
                oldest = min(self.states, key=lambda k: self.states[k]["touched"])
                self.states.pop(oldest)
            state = self.states.setdefault(key, {"touched": now})
            return self._check(payload, x, y, state, now)

    def _check(self, p, x, y, s, now):
        cfg = self.config
        result = dict(mode=cfg.uwb_speed_mode, accepted=False, applied=cfg.uwb_speed_mode == "observe",
                      reason=None, distance_m=None, dt_seconds=None, allowed_distance_m=None,
                      time_basis="device_monotonic_us", reference=None, reset_smoothing=False,
                      uwb_tag_id=p.uwb_tag_id, session_id=p.session_id, measurement_id=p.measurement_id,
                      max_speed_mps=cfg.uwb_max_speed_mps, margin_m=cfg.uwb_speed_margin_m,
                      consecutive_rejections=0, acquisition_samples=0, acquisition_span_seconds=0)

        def finish(reason, accepted=False, reset=False):
            result.update(reason=reason, accepted=accepted,
                          applied=accepted or cfg.uwb_speed_mode == "observe",
                          reset_smoothing=reset and cfg.uwb_speed_mode == "enforce",
                          consecutive_rejections=s.get("rejections", 0))
            return result

        if not all(math.isfinite(v) for v in (x, y)):
            # Never send non-finite coordinates into existing filters, even in observe mode.
            finish("nonfinite_candidate")
            result["applied"] = False
            return result
        if any(value is None for value in (p.session_id, p.measurement_id, p.cycle_id, p.measured_uptime_us)):
            return finish("measurement_clock_unavailable")

        identity = (p.uwb_tag_id, p.device_id, p.session_id)
        policy = tuple(getattr(cfg, name) for name in (
            "uwb_speed_mode", "uwb_max_speed_mps", "uwb_speed_margin_m", "uwb_speed_min_dt_seconds",
            "uwb_speed_max_gap_seconds", "uwb_speed_acquire_samples", "uwb_speed_acquire_span_seconds",
            "uwb_speed_acquire_margin_m", "uwb_speed_reacquire_rejections", "uwb_speed_reacquire_span_seconds"))
        reset_reason = None
        if s.get("identity") != identity or s.get("policy") != policy:
            same_device = s.get("identity", (None, None))[:2] == identity[:2]
            old_boot = SESSION_RE.fullmatch(s["identity"][2]) if same_device else None
            new_boot = SESSION_RE.fullmatch(p.session_id)
            if same_device and old_boot and new_boot and old_boot[1] == new_boot[1] and int(new_boot[2]) <= int(old_boot[2]) and s["identity"] != identity:
                return finish("older_or_conflicting_boot")
            if same_device and identity in s.get("retired", []):
                return finish("retired_session")
            retired = s.get("retired", [])
            if same_device and s.get("identity") != identity:
                retired = (retired + [s["identity"]])[-64:]
            reset_reason = "initial_acquisition" if "identity" not in s else (
                "policy_changed" if s["identity"] == identity else "tag_or_session_changed")
            s.clear()
            s.update(identity=identity, policy=policy, touched=now, retired=retired,
                     acquisition_reason=reset_reason, seen=[], rejections=0)

        t = p.measured_uptime_us / 1e6
        if p.measurement_id in s["seen"]:
            return finish("duplicate_measurement")
        if p.cycle_id <= s.get("last_cycle", -1):
            return finish("out_of_order_cycle")
        last_t = s.get("last_time")
        frame_dt = t-last_t if last_t is not None else None
        result["frame_dt_seconds"] = frame_dt
        if frame_dt is not None and frame_dt+1e-9 < cfg.uwb_speed_min_dt_seconds:
            s.pop("pending", None)
            return finish("non_increasing_or_short_dt")
        if (frame_dt is not None and frame_dt > cfg.uwb_speed_max_gap_seconds) or now-s["touched"] > cfg.uwb_speed_max_gap_seconds:
            s.pop("reference", None)
            s.pop("pending", None)
            s.update(rejections=0, acquisition_reason="long_gap_acquisition")
        s.update(last_time=t, last_cycle=p.cycle_id, touched=now)
        s["seen"] = (s["seen"] + [p.measurement_id])[-256:]
        reference = s.get("reference")
        if reference:
            dt = t-reference[2]
            result.update(reference={"x": reference[0], "y": reference[1], "measured_uptime_us": int(reference[2]*1e6)},
                          dt_seconds=dt, distance_m=math.hypot(x-reference[0], y-reference[1]),
                          allowed_distance_m=cfg.uwb_max_speed_mps*dt+cfg.uwb_speed_margin_m)
            # A long interval from the last *accepted* candidate is reacquired,
            # rather than allowing an indefinitely expanding jump radius.
            if dt > cfg.uwb_speed_max_gap_seconds:
                s.pop("reference")
                s.pop("pending", None)
                s.update(rejections=0, acquisition_reason="reference_expired_acquisition")
                reference = None
            elif result["distance_m"] <= result["allowed_distance_m"]+1e-9:
                s.update(reference=(x, y, t), rejections=0)
                s.pop("pending", None)
                return finish("within_speed_limit", accepted=True)
        if reference:
            s["rejections"] += 1
        pending = s.get("pending")
        if pending:
            step_dt, span = t-pending["last"][2], t-pending["first"][2]
            step = math.hypot(x-pending["last"][0], y-pending["last"][1])
            total = math.hypot(x-pending["first"][0], y-pending["first"][1])
            coherent = (step <= cfg.uwb_max_speed_mps*step_dt+cfg.uwb_speed_acquire_margin_m and
                        total <= cfg.uwb_max_speed_mps*span+cfg.uwb_speed_acquire_margin_m)
        else:
            coherent = False
        if not coherent:
            pending = {"first": (x, y, t), "last": (x, y, t), "count": 0}
        pending.update(last=(x, y, t), count=pending["count"]+1)
        s["pending"] = pending
        span = t-pending["first"][2]
        result.update(acquisition_samples=pending["count"], acquisition_span_seconds=span)
        required_span = cfg.uwb_speed_reacquire_span_seconds if reference else cfg.uwb_speed_acquire_span_seconds
        ready = pending["count"] >= cfg.uwb_speed_acquire_samples and span+1e-9 >= required_span
        if reference:
            ready = ready and s["rejections"] >= cfg.uwb_speed_reacquire_rejections
        if ready:
            reason = "reacquired_after_rejections" if reference else "acquired_"+s["acquisition_reason"]
            s.update(reference=(x, y, t), rejections=0)
            s.pop("pending", None)
            return finish(reason, accepted=True, reset=True)
        return finish("speed_exceeded" if reference else s["acquisition_reason"])


speed_guard = LocationSpeedGuard(settings)
