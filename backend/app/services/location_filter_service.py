import math
from collections import defaultdict, deque
from dataclasses import dataclass
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


def filter_location(worker_id: str, x: float, y: float, previous: tuple[float, float] | None) -> tuple[float, float]:
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
                state.last_mx, state.last_my = mx, my
                return state.x, state.y
            # Include an exact boundary such as 30 cm even when floating-point
            # arithmetic represents it as 0.299999999...
            if displacement + 1e-9 >= settings.location_move_start_m:
                state.move_samples += 1
            else:
                state.move_samples = 0
            state.last_mx, state.last_my = mx, my
            if state.move_samples < settings.location_move_confirm_samples:
                return state.x, state.y
            state.moving = True
            state.move_samples = 0
            state.quiet_samples = 0

        last_mx = mx if state.last_mx is None else state.last_mx
        last_my = my if state.last_my is None else state.last_my
        raw_step = math.hypot(mx - last_mx, my - last_my)
        if raw_step <= settings.location_stop_step_m:
            state.quiet_samples += 1
        else:
            state.quiet_samples = 0

        alpha = settings.location_ema_alpha
        state.x = state.x * (1 - alpha) + mx * alpha
        state.y = state.y * (1 - alpha) + my * alpha
        state.last_mx, state.last_my = mx, my
        if state.quiet_samples >= settings.location_stop_confirm_samples:
            state.moving = False
            state.quiet_samples = 0
        return state.x, state.y
