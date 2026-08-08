import math


def solve_position(anchors: list[dict], measurements: list[dict]) -> tuple[float, float, float]:
    """가중 Gauss-Newton 최소제곱. 유효 앵커가 3개 미만이면 예외."""
    anchor_map = {a["anchor_id"]: a for a in anchors}
    rows = [
        (anchor_map[m["anchor_id"]], m["distance_m"], max(0.05, m.get("quality", 1.0)))
        for m in measurements
        if m["anchor_id"] in anchor_map
    ]
    if len(rows) < 3:
        raise ValueError("유효한 UWB 앵커가 3개 미만입니다.")
    weight_sum = sum(weight for _, _, weight in rows)
    x = sum(anchor["x"] * weight for anchor, _, weight in rows) / weight_sum
    y = sum(anchor["y"] * weight for anchor, _, weight in rows) / weight_sum
    for _ in range(12):
        a11 = a12 = a22 = b1 = b2 = 0.0
        for anchor, distance, quality in rows:
            dx, dy = x - anchor["x"], y - anchor["y"]
            predicted = max(0.001, math.hypot(dx, dy))
            residual = distance - predicted
            jx, jy = dx / predicted, dy / predicted
            a11 += quality * jx * jx
            a12 += quality * jx * jy
            a22 += quality * jy * jy
            b1 += quality * jx * residual
            b2 += quality * jy * residual
        det = a11 * a22 - a12 * a12
        if abs(det) < 1e-9:
            break
        step_x = (b1 * a22 - b2 * a12) / det
        step_y = (a11 * b2 - a12 * b1) / det
        x += step_x
        y += step_y
        if math.hypot(step_x, step_y) < 0.001:
            break
    errors = [abs(math.hypot(x - a["x"], y - a["y"]) - d) for a, d, _ in rows]
    rmse = math.sqrt(sum(e * e for e in errors) / len(errors))
    confidence = max(0.05, min(1.0, 1.0 - rmse / 3.0))
    return round(x, 3), round(y, 3), round(confidence, 3)

