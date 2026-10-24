"""Reject isolated candidate jumps before the existing 30cm motion filter."""
import math
import time
from threading import Lock

from ..config import settings


class PositionJumpGuard:
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
        key = (payload.organization_id, payload.site_id, payload.worker_id, payload.device_id)
        clock = payload.measured_uptime_us
        t = clock/1e6 if clock is not None else now
        identity = (payload.uwb_tag_id, payload.session_id, clock is not None)
        policy = (cfg.uwb_jump_mode, cfg.uwb_jump_speed_mps, cfg.uwb_jump_margin_m,
                  cfg.uwb_jump_max_step_m, cfg.uwb_jump_confirm_samples,
                  cfg.uwb_jump_confirm_seconds, cfg.uwb_jump_reset_gap_seconds)
        with self.lock:
            self.states = {k:v for k,v in self.states.items() if now-v['touched'] < cfg.uwb_speed_state_ttl_seconds}
            if key not in self.states and len(self.states) >= cfg.uwb_filter_max_tags:
                self.states.pop(min(self.states, key=lambda k:self.states[k]['touched']))
            s = self.states.get(key)
            if s is None or s['identity'] != identity or s['policy'] != policy:
                s = dict(identity=identity, policy=policy, touched=now)
                self.states[key] = s
            result = dict(mode=cfg.uwb_jump_mode, candidate={'x':x if math.isfinite(x) else None,
                                                         'y':y if math.isfinite(y) else None},
                          reference=None, distance_m=None, dt_seconds=None,
                          allowed_distance_m=None, confirmation_samples=0,
                          confirmation_seconds=0, time_basis='device_uptime' if clock is not None else 'server_monotonic')

            def finish(accepted, reason):
                return dict(result, accepted=accepted, applied=accepted or cfg.uwb_jump_mode == 'observe', reason=reason)

            if not all(math.isfinite(v) for v in (x,y,t)):
                return dict(finish(False, 'nonfinite_candidate'), applied=False)
            if t <= s.get('last_time', -math.inf):
                return dict(finish(False, 'non_increasing_clock'), applied=False)
            if now-s['touched'] > cfg.uwb_jump_reset_gap_seconds or t-s.get('last_time', t) > cfg.uwb_jump_reset_gap_seconds:
                s.pop('reference', None)
                s.pop('pending', None)
            s.update(touched=now, last_time=t)
            reference = s.get('reference')
            if reference:
                dt = t-reference[2]
                distance = math.hypot(x-reference[0], y-reference[1])
                allowed = min(cfg.uwb_jump_max_step_m, cfg.uwb_jump_speed_mps*dt+cfg.uwb_jump_margin_m)
                result.update(reference={'x':reference[0], 'y':reference[1]},
                              distance_m=round(distance, 6), dt_seconds=round(dt, 6),
                              allowed_distance_m=round(allowed, 6))
                if distance <= allowed+1e-9:
                    s['reference'] = (x,y,t)
                    s.pop('pending', None)
                    return finish(True, 'continuous_motion')
            pending = s.get('pending')
            if pending:
                last = pending['last']
                coherent = math.hypot(x-last[0], y-last[1]) <= min(
                    cfg.uwb_jump_max_step_m,
                    cfg.uwb_jump_speed_mps*(t-last[2])+cfg.uwb_jump_margin_m)
            else:
                coherent = False
            if not coherent:
                pending = dict(first=t, count=0)
            pending.update(last=(x,y,t), count=pending['count']+1)
            s['pending'] = pending
            span = t-pending['first']
            result.update(confirmation_samples=pending['count'], confirmation_seconds=round(span, 6))
            if pending['count'] >= cfg.uwb_jump_confirm_samples and span+1e-9 >= cfg.uwb_jump_confirm_seconds:
                s['reference'] = (x,y,t)
                s.pop('pending', None)
                return finish(True, 'jump_reconfirmed' if reference else 'initial_position_confirmed')
            return finish(False, 'jump_pending' if reference else 'initial_position_pending')


jump_guard = PositionJumpGuard(settings)
