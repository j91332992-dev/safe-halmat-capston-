import math
from ..config import settings


class PositionSolveError(ValueError):
    def __init__(self, reason, message, **diagnostics):
        super().__init__(message)
        self.reason = reason
        self.diagnostics = diagnostics


def solution_diagnostics(anchors, measurements, x, y):
    anchor_map = {a['anchor_id']: a for a in anchors}
    rows = []
    for m in measurements:
        a = anchor_map.get(m['anchor_id'])
        if not a or m.get('excluded'):
            continue
        predicted = math.hypot(x-a['x'], y-a['y'])
        rows.append(dict(anchor_id=m['anchor_id'], distance_m=m['distance_m'],
                         predicted_distance_m=round(predicted, 6),
                         residual_m=round(predicted-m['distance_m'], 6),
                         weight=m.get('quality', 1.0)))
    weight_sum = sum(max(.05, r['weight']) for r in rows)
    return dict(anchors=rows,
        rmse_m=round(math.sqrt(sum(r['residual_m']**2 for r in rows)/len(rows)), 6) if rows else None,
        weighted_rmse_m=round(math.sqrt(sum(max(.05,r['weight'])*r['residual_m']**2 for r in rows)/weight_sum), 6) if weight_sum else None)


def solve_position(anchors: list[dict], measurements: list[dict]) -> tuple[float, float, float]:
    """가중 Gauss-Newton 최소제곱. 유효 앵커가 3개 미만이면 예외."""
    anchor_map = {a["anchor_id"]: a for a in anchors}
    rows = [
        (anchor_map[m["anchor_id"]], m["distance_m"], max(0.05, m.get("quality", 1.0)))
        for m in measurements
        if m["anchor_id"] in anchor_map and not m.get("excluded", False)
    ]
    ids = [a["anchor_id"] for a, _, _ in rows]
    if len(set(ids)) < 3:
        raise PositionSolveError("insufficient_anchors", "유효한 서로 다른 UWB 앵커가 3개 미만입니다.", used_anchor_ids=sorted(set(ids)))
    if len(set(ids)) != len(ids):
        raise PositionSolveError("duplicate_anchors", "중복 앵커 측정으로 위치를 확정할 수 없습니다.")
    if any(not all(math.isfinite(v) for v in (a["x"], a["y"], d, w)) or d <= 0 for a, d, w in rows):
        raise PositionSolveError("nonfinite_input", "위치 계산 입력이 유효하지 않습니다.")
    weight_sum = sum(weight for _, _, weight in rows)
    x = sum(anchor["x"] * weight for anchor, _, weight in rows) / weight_sum
    y = sum(anchor["y"] * weight for anchor, _, weight in rows) / weight_sum
    converged = False
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
        geometry_ratio = det / max((a11+a22)**2, 1e-30)
        if abs(det) < 1e-9 or geometry_ratio < settings.uwb_solver_min_geometry_ratio:
            raise PositionSolveError("singular_geometry", "앵커 배치 또는 후보 위치의 계산 조건이 불안정합니다.",
                                     geometry_ratio=geometry_ratio, threshold=settings.uwb_solver_min_geometry_ratio)
        step_x = (b1 * a22 - b2 * a12) / det
        step_y = (a11 * b2 - a12 * b1) / det
        x += step_x
        y += step_y
        if math.hypot(step_x, step_y) < 0.001:
            converged = True
            break
    if not all(math.isfinite(v) for v in (x, y)):
        raise PositionSolveError("nonfinite_solution", "위치 계산 결과가 유효하지 않습니다.")
    if not converged:
        raise PositionSolveError("nonconverged", "기존 위치 계산이 제한 회차 안에 수렴하지 않았습니다.", iterations=12)
    errors = [abs(math.hypot(x - a["x"], y - a["y"]) - d) for a, d, _ in rows]
    rmse = math.sqrt(sum(e * e for e in errors) / len(errors))
    if not math.isfinite(rmse):
        raise PositionSolveError("nonfinite_solution", "위치 잔차 계산 결과가 유효하지 않습니다.")
    if rmse > settings.uwb_solver_max_rmse_m:
        raise PositionSolveError("high_residual", "거리와 후보 위치의 잔차가 허용값을 초과했습니다.",
                                 rmse_m=rmse, threshold_m=settings.uwb_solver_max_rmse_m)
    confidence = max(0.05, min(1.0, 1.0 - rmse / 3.0))
    return round(x, 3), round(y, 3), round(confidence, 3)

