"""Route-only boundary correction; never changes the measured worker position."""
import math

BOUNDARY_DEPTH_M = .25
MAX_CORRECTION_M = .80  # depth + clearance + grid quantization; not a position tolerance


def corrected_start(x, y, objects, width, height, grid, clearance, blocked, history, escape_blocked=None):
    info = {"applied": False, "original": {"x": x, "y": y},
            "depth_limit_m": BOUNDARY_DEPTH_M, "distance_m": 0.0}
    if not (0 <= x <= width and 0 <= y <= height):
        return None, {**info, "reason": "outside_map"}
    nearby = [o for o in objects if o.object_type in {"wall", "obstacle"}
              and o.x-clearance <= x <= o.x+o.width+clearance
              and o.y-clearance <= y <= o.y+o.height+clearance]
    if len(nearby) != 1:
        return None, {**info, "reason": "ambiguous_or_non_obstacle_block"}
    o = nearby[0]
    sides = {"left": o.x-x, "right": x-o.x-o.width,
             "bottom": o.y-y, "top": y-o.y-o.height}
    outside = [side for side, distance in sides.items() if distance > 0]
    if outside:
        if len(outside) != 1:
            return None, {**info, "reason": "ambiguous_corner"}
        side = outside[0]
        depth = 0.
        evidence = "outside_obstacle_in_clearance"
    else:
        depth = -max(sides.values())
        if depth > BOUNDARY_DEPTH_M + 1e-8:
            return None, {**info, "reason": "deep_inside", "depth_m": depth}
        candidates = [s for s, d in sides.items() if -d <= BOUNDARY_DEPTH_M + 1e-8]
        supported = []
        for s in candidates:
            def same_side(h):
                hx, hy = h
                return {"left": hx < o.x-clearance, "right": hx > o.x+o.width+clearance,
                        "bottom": hy < o.y-clearance, "top": hy > o.y+o.height+clearance}[s]
            if any(same_side(h) and math.hypot(h[0]-x, h[1]-y) <= 1.0 for h in history):
                supported.append(s)
        if len(supported) != 1:
            return None, {**info, "reason": "missing_or_ambiguous_recent_side", "depth_m": depth}
        side = supported[0]
        evidence = "recent_clear_position_same_side"
    options = []
    for ix in range(max(0, int((x-MAX_CORRECTION_M)/grid)), min(int(width/grid), int((x+MAX_CORRECTION_M)/grid))+1):
        for iy in range(max(0, int((y-MAX_CORRECTION_M)/grid)), min(int(height/grid), int((y+MAX_CORRECTION_M)/grid))+1):
            px, py = ix*grid, iy*grid
            same = {"left": px < o.x-clearance, "right": px > o.x+o.width+clearance,
                    "bottom": py < o.y-clearance, "top": py > o.y+o.height+clearance}[side]
            tangent = abs(py-y) if side in {"left", "right"} else abs(px-x)
            distance = math.hypot(px-x, py-y)
            if same and tangent <= grid and distance <= MAX_CORRECTION_M and not blocked(px, py):
                if escape_blocked and any(escape_blocked(x+(px-x)*t/40, y+(py-y)*t/40, o.obstacle_id) for t in range(41)):
                    continue
                options.append((distance, ix, iy))
    if not options:
        return None, {**info, "reason": "no_clear_same_side_cell", "depth_m": depth}
    distance, ix, iy = min(options)
    return (ix, iy), {**info, "applied": True, "reason": evidence, "side": side,
                     "obstacle_id": o.obstacle_id, "depth_m": round(depth, 4),
                     "distance_m": round(distance, 4), "corrected": {"x": ix*grid, "y": iy*grid}}
