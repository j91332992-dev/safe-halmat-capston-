"""Keep a checked polyline while the worker follows its corridor, not exact points."""
import math
from .evacuation_service import _blocked

CORRIDOR_HALF_WIDTH_M = 0.30


def follow_corridor(route, state, origin, objects, fire_zone, width, height):
    def clear(a, b):
        length = math.hypot(b["x"]-a["x"], b["y"]-a["y"])
        steps = max(1, math.ceil(length / 0.05))
        for i in range(steps+1):
            t = i / steps
            x, y = a["x"] + t*(b["x"]-a["x"]), a["y"] + t*(b["y"]-a["y"])
            if not (0 <= x <= width and 0 <= y <= height) or _blocked(x, y, objects, fire_zone):
                return False
        return True

    old = state.get("corridor_path") or []
    candidates = []
    if state.get("exit_id") == route.get("exit_id"):
        # Only the current and following segment; never jump to a distant leg.
        for i in range(min(2, len(old)-1)):
            a, b = old[i], old[i+1]
            dx, dy = b["x"]-a["x"], b["y"]-a["y"]
            length2 = dx*dx + dy*dy
            if length2 < 1e-8:
                continue
            t = max(0., min(1., ((origin["x"]-a["x"])*dx + (origin["y"]-a["y"])*dy)/length2))
            q = {"x": a["x"]+t*dx, "y": a["y"]+t*dy}
            lateral = math.hypot(origin["x"]-q["x"], origin["y"]-q["y"])
            remaining = [q, *old[i+1:]]
            if (lateral <= CORRIDOR_HALF_WIDTH_M and clear(origin, q) and clear(origin, b)
                    and all(clear(u, v) for u, v in zip(remaining, remaining[1:]))):
                candidates.append((lateral, i, remaining))
    if candidates:
        lateral, _, path = min(candidates, key=lambda item: item[0])
        # Keep right-angle vertices. Do not replace a nearby corner with a
        # diagonal shortcut from the measured worker position.
        while len(path) > 1 and math.hypot(path[1]["x"]-path[0]["x"], path[1]["y"]-path[0]["y"]) < .05:
            path = path[1:]
        route["path"] = path
        route["distance_m"] = round(lateral + sum(math.hypot(b["x"]-a["x"], b["y"]-a["y"]) for a,b in zip(path,path[1:])), 2)
        status = "following"
    else:
        lateral = None
        path = route["path"]
        status = "replanned" if old else "planned"
    state.update(corridor_path=path, exit_id=route.get("exit_id"))
    route.update(corridor_half_width_m=CORRIDOR_HALF_WIDTH_M,
                 corridor_status=status, cross_track_error_m=round(lateral, 3) if lateral is not None else None,
                 corridor_note="경로 추종 허용 범위이며 실제 안전 통로 폭을 보장하지 않습니다.")
    return route
