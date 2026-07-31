from collections import defaultdict, deque
from statistics import median

from ..config import settings


_history: dict[str, deque[tuple[float, float]]] = defaultdict(lambda: deque(maxlen=5))


def filter_location(worker_id: str, x: float, y: float, previous: tuple[float, float] | None) -> tuple[float, float]:
    history = _history[worker_id]
    history.append((x, y))
    mx = median(item[0] for item in history)
    my = median(item[1] for item in history)
    if previous is None:
        return mx, my
    alpha = settings.location_ema_alpha
    return previous[0] * (1 - alpha) + mx * alpha, previous[1] * (1 - alpha) + my * alpha

