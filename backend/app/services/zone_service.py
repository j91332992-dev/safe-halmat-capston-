from collections import defaultdict
import json
import math


_inside_counts: dict[tuple[str, str], int] = defaultdict(int)
_outside_counts: dict[tuple[str, str], int] = defaultdict(int)


def point_in_zone(x: float, y: float, zone) -> bool:
    coords = json.loads(zone.coordinates_json)
    if zone.zone_type == "rectangle":
        return coords["x"] <= x <= coords["x"] + coords["width"] and coords["y"] <= y <= coords["y"] + coords["height"]
    if zone.zone_type == "circle":
        return math.hypot(x - coords["x"], y - coords["y"]) <= coords["radius"]
    points = coords.get("points", [])
    inside = False
    j = len(points) - 1
    for i in range(len(points)):
        xi, yi = points[i]["x"], points[i]["y"]
        xj, yj = points[j]["x"], points[j]["y"]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / max(1e-9, yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def confirm_zone(worker_id: str, zone, inside: bool, currently_inside: bool) -> tuple[bool, str | None]:
    key = (worker_id, zone.zone_id)
    if inside:
        _inside_counts[key] += 1
        _outside_counts[key] = 0
        if not currently_inside and _inside_counts[key] >= 3:
            return True, "ZONE_ENTERED"
    else:
        _outside_counts[key] += 1
        _inside_counts[key] = 0
        if currently_inside and _outside_counts[key] >= 3:
            return False, "ZONE_EXITED"
    return currently_inside, None

