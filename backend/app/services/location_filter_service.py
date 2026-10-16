import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from statistics import median
from threading import Lock

from ..config import settings


_history: dict[str, deque[tuple[float, float]]] = defaultdict(lambda: deque(maxlen=3))


@dataclass
class MotionState:
    x: float
    y: float
    moving: bool = False
    move_samples: int = 0
    quiet_samples: int = 0
    stop_window: deque = field(default_factory=lambda: deque(maxlen=64))
    pending_direction: tuple[float, float] | None = None
    last_mx: float | None = None
    last_my: float | None = None


_states: dict[str, MotionState] = {}
_lock = Lock()


def reset_location_filter(worker_id: str | None = None) -> None:
    """Reset state for tests, layout changes, or a newly assigned tag."""
    with _lock:
        if worker_id is None:
            _history.clear()
            _states.clear()
        else:
            _history.pop(worker_id, None)
            _states.pop(worker_id, None)


def filter_location(worker_id: str, x: float, y: float, previous: tuple[float, float] | None, *, now: float | None = None) -> tuple[float, float]:
    now = time.monotonic() if now is None else now
    with _lock:
        history = _history[worker_id]
        history.append((x, y))
        mx = float(median(item[0] for item in history))
        my = float(median(item[1] for item in history))

        state = _states.get(worker_id)
        if state is None:
            initial = previous if previous is not None else (mx, my)
            state = MotionState(float(initial[0]), float(initial[1]), last_mx=mx, last_my=my)
            _states[worker_id] = state
            if previous is None:
                return mx, my

        displacement = math.hypot(mx - state.x, my - state.y)
        if not state.moving:
            if displacement <= settings.location_stationary_radius_m:
                state.move_samples = 0
                state.pending_direction = None
                state.last_mx, state.last_my = mx, my
                return state.x, state.y
            # Include an exact boundary such as 30 cm even when floating-point
            # arithmetic represents it as 0.299999999...
            if displacement + 1e-9 >= settings.location_move_start_m:
                direction = ((mx-state.x)/displacement, (my-state.y)/displacement)
                prior = state.pending_direction
                # Reject alternating jumps; confirm within roughly 37 degrees.
                aligned = prior is not None and direction[0]*prior[0] + direction[1]*prior[1] >= .8
                state.move_samples = state.move_samples + 1 if aligned else 1
                if not aligned:
                    state.pending_direction = direction
            else:
                state.move_samples = 0
                state.pending_direction = None
            state.last_mx, state.last_my = mx, my
            if state.move_samples < settings.location_move_confirm_samples:
                return state.x, state.y
            state.moving = True
            state.move_samples = 0
            state.quiet_samples = 0
            state.stop_window.clear()

        # Judge stillness over elapsed time, not movement per sample.
        # A receive gap is not evidence that the worker stopped.
        window = state.stop_window
        if window and (now <= window[-1][0] or now-window[-1][0] > .5):
            window.clear()
        window.append((now, mx, my))
        duration = settings.location_stop_window_seconds
        while len(window) > 2 and now-window[1][0] >= duration:
            window.popleft()
        span = now-window[0][0]
        spread = math.hypot(max(p[1] for p in window)-min(p[1] for p in window),
                            max(p[2] for p in window)-min(p[2] for p in window))
        older = [p for p in window if p[0] <= now-duration/2]
        newer = [p for p in window if p[0] > now-duration/2]
        # Compare half-window medians: stationary range noise can fluctuate,
        # but continued movement must not be mistaken for repeated tiny steps.
        net = math.inf
        if older and newer:
            net = math.hypot(median(p[1] for p in newer)-median(p[1] for p in older),
                             median(p[2] for p in newer)-median(p[2] for p in older))
        stopped = (len(window) >= 3 and span + 1e-9 >= duration
                   and spread <= settings.location_stop_spread_m
                   and net <= settings.location_stop_net_m)

        alpha = settings.location_ema_alpha
        state.x = state.x * (1 - alpha) + mx * alpha
        state.y = state.y * (1 - alpha) + my * alpha
        state.last_mx, state.last_my = mx, my
        if stopped:
            state.moving = False
            state.stop_window.clear()
            state.quiet_samples = 0
        return state.x, state.y


def location_motion_status(worker_id: str) -> dict:
    with _lock:
        state = _states.get(worker_id)
        if state is None:
            return {"mode": "uninitialized"}
        return {"mode": "moving" if state.moving else "stationary",
                "move_confirmation_samples": state.move_samples,
                "stop_window_samples": len(state.stop_window),
                "stop_window_seconds": (state.stop_window[-1][0]-state.stop_window[0][0]) if state.stop_window else 0}
