from __future__ import annotations

from datetime import datetime, timedelta
import heapq
import json
import math
from uuid import uuid4

from sqlalchemy.orm import Session

from ..config import settings
from ..models.entities import EvacuationIncident, Obstacle, SiteLayout, WorkerState

GRID_M = 0.20
WORKER_CLEARANCE_M = 0.25
FIRE_CLEARANCE_M = 0.75
ACTIVE_STATUSES = ("pending_manager", "active")


def incident_to_dict(item: EvacuationIncident | None) -> dict | None:
    if not item:
        return None
    return {
        "incident_id": item.incident_id,
        "worker_id": item.worker_id,
        "source": item.source,
        "status": item.status,
        "fire_zone": json.loads(item.fire_zone_json or "{}") or None,
        "details": json.loads(item.details_json or "{}"),
        "cancel_reason": item.cancel_reason,
        "created_at": item.created_at.isoformat() + "Z",
        "updated_at": item.updated_at.isoformat() + "Z",
    }


def current_incident(db: Session) -> EvacuationIncident | None:
    return (
        db.query(EvacuationIncident)
        .filter(EvacuationIncident.status.in_(ACTIVE_STATUSES))
        .order_by(EvacuationIncident.created_at.desc())
        .first()
    )


def trigger_fire(db: Session, source: str, worker_id: str | None, details: dict | None = None) -> tuple[EvacuationIncident, bool]:
    current = current_incident(db)
    if not current and source == "yolo":
        recently_cancelled = (
            db.query(EvacuationIncident)
            .filter(
                EvacuationIncident.status == "cancelled",
                EvacuationIncident.cancel_reason.in_(("false_alarm", "no_fire")),
                EvacuationIncident.updated_at >= datetime.utcnow() - timedelta(seconds=30),
            )
            .order_by(EvacuationIncident.updated_at.desc())
            .first()
        )
        if recently_cancelled:
            return recently_cancelled, False
    if current:
        merged = json.loads(current.details_json or "{}")
        merged.setdefault("additional_sources", []).append({"source": source, "worker_id": worker_id})
        current.details_json = json.dumps(merged, ensure_ascii=False)
        current.updated_at = datetime.utcnow()
        db.flush()
        return current, False
    item = EvacuationIncident(
        incident_id="fire-" + uuid4().hex,
        worker_id=worker_id,
        source=source,
        status="pending_manager",
        fire_zone_json="{}",
        details_json=json.dumps(details or {}, ensure_ascii=False),
    )
    db.add(item)
    db.flush()
    return item, True


def set_fire_zone(item: EvacuationIncident, zone: dict) -> None:
    item.fire_zone_json = json.dumps(zone, ensure_ascii=False)
    item.status = "active"
    item.cancel_reason = None
    item.updated_at = datetime.utcnow()


def cancel_incident(item: EvacuationIncident, reason: str) -> None:
    item.status = "resolved" if reason == "resolved" else "cancelled"
    item.cancel_reason = reason
    item.updated_at = datetime.utcnow()


def _inside_rect(x: float, y: float, rect: dict, padding: float = 0.0) -> bool:
    return (
        float(rect.get("x", 0)) - padding <= x <= float(rect.get("x", 0)) + float(rect.get("width", 0)) + padding
        and float(rect.get("y", 0)) - padding <= y <= float(rect.get("y", 0)) + float(rect.get("height", 0)) + padding
    )


def _blocked(x: float, y: float, structures: list[Obstacle], fire_zone: dict | None) -> bool:
    for item in structures:
        if item.object_type not in {"obstacle", "wall"}:
            continue
        rect = {"x": item.x, "y": item.y, "width": item.width, "height": item.height}
        if _inside_rect(x, y, rect, WORKER_CLEARANCE_M):
            return True
    return bool(fire_zone and _inside_rect(x, y, fire_zone, FIRE_CLEARANCE_M))


def _nearest_open(cell: tuple[int, int], is_blocked, max_x: int, max_y: int) -> tuple[int, int] | None:
    if not is_blocked(cell):
        return cell
    for radius in range(1, 12):
        for dx in range(-radius, radius + 1):
            for dy in (-radius, radius):
                candidate = (cell[0] + dx, cell[1] + dy)
                if 0 <= candidate[0] <= max_x and 0 <= candidate[1] <= max_y and not is_blocked(candidate):
                    return candidate
        for dy in range(-radius + 1, radius):
            for dx in (-radius, radius):
                candidate = (cell[0] + dx, cell[1] + dy)
                if 0 <= candidate[0] <= max_x and 0 <= candidate[1] <= max_y and not is_blocked(candidate):
                    return candidate
    return None


def _simplify(points: list[dict]) -> list[dict]:
    if len(points) < 3:
        return points
    result = [points[0]]
    previous_direction = None
    for index in range(1, len(points)):
        dx = round(points[index]["x"] - points[index - 1]["x"], 3)
        dy = round(points[index]["y"] - points[index - 1]["y"], 3)
        direction = (0 if abs(dx) < 0.01 else int(math.copysign(1, dx)), 0 if abs(dy) < 0.01 else int(math.copysign(1, dy)))
        if previous_direction is not None and direction != previous_direction:
            result.append(points[index - 1])
        previous_direction = direction
    result.append(points[-1])
    return result


def _fire_details(worker: WorkerState, fire_zone: dict | None) -> tuple[str, float | None]:
    if not fire_zone:
        return "화재 발생 위치 확인 중", None
    name = str(fire_zone.get("name") or "관리자 지정 화재구역").strip() or "관리자 지정 화재구역"
    center_x = float(fire_zone.get("x", 0)) + float(fire_zone.get("width", 0)) / 2
    center_y = float(fire_zone.get("y", 0)) + float(fire_zone.get("height", 0)) / 2
    return name, round(math.hypot(worker.x - center_x, worker.y - center_y), 2)


def _alert_result(
    worker: WorkerState,
    fire_zone: dict | None,
    *,
    available: bool,
    exit_name: str | None = None,
    distance_m: float | None = None,
    reason: str | None = None,
) -> dict:
    fire_name, fire_distance = _fire_details(worker, fire_zone)
    if fire_zone is None:
        fire_message = "화재가 감지되었습니다. 발생 위치를 확인 중입니다."
    elif fire_distance is not None and fire_distance <= 3.0:
        fire_message = f"화재가 {fire_name}, 작업자 근처에서 발생했습니다."
    else:
        fire_message = f"화재가 {fire_name}에서 발생했으며 작업자 위치와 약 {fire_distance:.1f}미터 떨어져 있습니다."
    if available and exit_name is not None and distance_m is not None:
        exit_message = f"가장 가까운 비상구는 {exit_name}이며 이동거리는 약 {distance_m:.1f}미터입니다."
    else:
        exit_message = "가장 가까운 비상구 거리를 계산할 수 없습니다."
    message = f"{fire_message} {exit_message} 비상 유도등을 확인하고 즉시 대피하세요."
    return {
        "worker_id": worker.worker_id,
        "available": available,
        "mode": "fire_confirmed" if fire_zone else "fire_unconfirmed",
        "exit_name": exit_name,
        "distance_m": distance_m,
        "path": [],
        "instructions": [message],
        "message": message,
        "reason": reason,
        "fire_zone": fire_zone,
        "fire_location_name": fire_name,
        "fire_distance_m": fire_distance,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }


def calculate_route(db: Session, worker: WorkerState, incident: EvacuationIncident | None = None) -> dict:
    layout = db.get(SiteLayout, settings.site_id)
    width = layout.width if layout else settings.site_width_m
    height = layout.height if layout else settings.site_height_m
    objects = db.query(Obstacle).filter(Obstacle.site_id == settings.site_id).all()
    exits = [item for item in objects if item.object_type == "emergency_exit"]
    fire_zone = None
    if incident and incident.status == "active":
        fire_zone = json.loads(incident.fire_zone_json or "{}") or None
    if not exits:
        return _alert_result(worker, fire_zone, available=False, reason="지도에 비상구가 지정되지 않았습니다.")

    max_x, max_y = round(width / GRID_M), round(height / GRID_M)
    to_cell = lambda x, y: (max(0, min(max_x, round(x / GRID_M))), max(0, min(max_y, round(y / GRID_M))))
    to_point = lambda cell: {"x": round(cell[0] * GRID_M, 2), "y": round(cell[1] * GRID_M, 2)}
    blocked = lambda cell: _blocked(cell[0] * GRID_M, cell[1] * GRID_M, objects, fire_zone)
    start = _nearest_open(to_cell(worker.x, worker.y), blocked, max_x, max_y)
    if start is None:
        return _alert_result(worker, fire_zone, available=False, reason="현재 위치 주변에 이동 가능한 공간이 없습니다.")

    candidates = []
    for exit_item in exits:
        target_raw = to_cell(exit_item.x + exit_item.width / 2, exit_item.y + exit_item.height / 2)
        target = _nearest_open(target_raw, blocked, max_x, max_y)
        if target:
            candidates.append((exit_item, target))
    if not candidates:
        return _alert_result(worker, fire_zone, available=False, reason="화재구간으로 인해 사용 가능한 비상구가 없습니다.")

    goals = {cell: item for item, cell in candidates}
    open_heap = [(0.0, start)]
    cost = {start: 0.0}
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    goal = None
    directions = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414))

    while open_heap:
        _, current = heapq.heappop(open_heap)
        if current in goals:
            goal = current
            break
        for dx, dy, step in directions:
            nxt = (current[0] + dx, current[1] + dy)
            if not (0 <= nxt[0] <= max_x and 0 <= nxt[1] <= max_y) or blocked(nxt):
                continue
            if dx and dy and (blocked((current[0] + dx, current[1])) or blocked((current[0], current[1] + dy))):
                continue
            new_cost = cost[current] + step
            if new_cost >= cost.get(nxt, float("inf")):
                continue
            cost[nxt] = new_cost
            came_from[nxt] = current
            heuristic = min(math.hypot(nxt[0] - cell[0], nxt[1] - cell[1]) for cell in goals)
            heapq.heappush(open_heap, (new_cost + heuristic, nxt))

    if goal is None:
        return _alert_result(worker, fire_zone, available=False, reason="현재 구조와 화재구간을 고려한 비상구 거리를 계산하지 못했습니다.")

    cells = [goal]
    while cells[-1] != start:
        cells.append(came_from[cells[-1]])
    cells.reverse()
    exit_item = goals[goal]
    total_m = round(cost[goal] * GRID_M, 2)
    result = _alert_result(worker, fire_zone, available=True, exit_name=exit_item.name, distance_m=total_m)
    result["exit_id"] = exit_item.obstacle_id
    return result


def evacuation_snapshot(db: Session) -> dict:
    incident = current_incident(db)
    if not incident:
        return {"incident": None, "routes": {}}
    routes = {worker.worker_id: calculate_route(db, worker, incident) for worker in db.query(WorkerState).all()}
    return {"incident": incident_to_dict(incident), "routes": routes}


