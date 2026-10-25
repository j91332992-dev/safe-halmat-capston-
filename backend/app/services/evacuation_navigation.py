"""Bounded, opt-in live map guidance. No LLM in the steering loop."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import time
from datetime import datetime, timezone

from ..config import BASE_DIR
from ..database import SessionLocal
from ..models.entities import Device, EvacuationIncident, Obstacle, SiteLayout, WorkerState
from ..websocket import manager
from .evacuation_service import calculate_route, incident_to_dict
from .evacuation_corridor import follow_corridor
from .evacuation_guidance_service import send_helmet_guidance
from .serializers import device_to_dict
from .uwb_log_service import BoundedJsonlLog

_pending: dict = {}

_latest: dict[str, dict] = {}
_state: dict[str, dict] = {}
_log = BoundedJsonlLog(BASE_DIR / "logs" / "evacuation-navigation.jsonl", expiry_check_seconds=60)


def map_signature(db, site_id):
    layout = db.get(SiteLayout, site_id)
    objects = db.query(Obstacle).filter(Obstacle.site_id == site_id).order_by(Obstacle.obstacle_id).all()
    data = [([layout.width, layout.height] if layout else None),
            [[o.obstacle_id, o.object_type, o.x, o.y, o.width, o.height] for o in objects]]
    return hashlib.sha256(json.dumps(data).encode()).hexdigest()


def age(value):
    if value is None:
        return float("inf")
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return float("inf")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return max(0., (datetime.now(timezone.utc) - value).total_seconds())


def latest_route(worker_id):
    item = _latest.get(worker_id)
    return item if item and age(item.get("updated_at")) < 2 else None


def clear_navigation():
    _latest.clear()
    _state.clear()


def navigation_step(db, worker, incident, signature):
    started = time.monotonic()
    details = json.loads(incident.details_json or "{}")
    key = f"{incident.incident_id}:{worker.worker_id}"
    state = _state.setdefault(key, {"started_at": started})
    device = db.query(Device).filter(Device.worker_id == worker.worker_id,
                                    Device.site_id == worker.site_id,
                                    Device.device_type == "assistant_device").first()
    heading = device_to_dict(device) if device else {}
    location_age = age(worker.last_valid_location_at)
    heading_age = age(heading.get("heading_at"))
    route = {"worker_id": worker.worker_id, "available": False, "path": [],
             "mode": "fire_confirmed" if incident.status == "active" else "fire_unconfirmed"}
    action, message = "unavailable", "경로를 확인할 수 없습니다."
    if details.get("navigation_map_signature") != signature:
        action = "map_unverified"
        message = "지도와 비상구 확인이 필요하여 방향 안내를 할 수 없습니다."
    elif location_age > 1.5:
        action, message = "location_stale", "위치 확인 중입니다."
    elif heading_age > 1.0 or heading.get("heading_deg") is None:
        action, message = "heading_stale", "방향 확인 중입니다."
    else:
        # Route is recomputed off the UWB ingestion loop. Fixed upper frequency 2Hz.
        route = calculate_route(db, worker, incident)
        if route.get("available") and route.get("path"):
            layout = db.get(SiteLayout, worker.site_id)
            from ..config import settings
            objects = db.query(Obstacle).filter(Obstacle.site_id == worker.site_id).all()
            fire_zone = json.loads(incident.fire_zone_json or "{}") if incident.status == "active" else None
            origin = route.get("route_origin") if route.get("start_correction", {}).get("applied") else {"x": worker.x, "y": worker.y}
            route = follow_corridor(route, state, origin, objects, fire_zone,
                layout.width if layout else settings.site_width_m,
                layout.height if layout else settings.site_height_m)
        path = route.get("path") or []
        if not route.get("available") or not path:
            action, message = "no_route", "대피 경로 확인이 필요합니다."
        elif (route.get("distance_m") or 0) <= .5:
            action, message = "exit_near", "등록된 비상구 근처입니다. 실제 출구와 통행 가능 여부를 확인하세요."
        else:
            # First bend is never skipped by a lookahead through a wall.
            target = path[1] if len(path) > 1 else path[0]
            origin = (route.get("route_origin") if route.get("start_correction", {}).get("applied") else None) or {"x": worker.x, "y": worker.y}
            # Follow the checked segment bearing, not a diagonal to its endpoint
            # caused by a small UWB lateral offset inside the corridor.
            segment_origin = path[0]
            dx, dy = target["x"] - segment_origin["x"], target["y"] - segment_origin["y"]
            bearing = math.degrees(math.atan2(dy, dx)) % 360
            delta = (bearing - heading["heading_deg"] + 180) % 360 - 180
            distance = math.hypot(dx, dy)
            if abs(delta) <= 25:
                action, message = "forward", "벽면을 따라 앞으로 가세요."
                if len(path) > 2 and distance < 1.5:
                    nxt = path[2]
                    following = math.degrees(math.atan2(nxt["y"] - target["y"], nxt["x"] - target["x"]))
                    turn = (following - bearing + 180) % 360 - 180
                    if abs(turn) > 35:
                        action = "prepare_left" if turn > 0 else "prepare_right"
                        message = "앞으로 간 뒤 왼쪽으로 90도 돌아가세요." if turn > 0 else "앞으로 간 뒤 오른쪽으로 90도 돌아가세요."
            elif abs(delta) >= 155:
                action, message = "turn_back", "오른쪽으로 90도씩 두 번 돌아가세요."
            elif 65 <= abs(delta) <= 115:
                action = "turn_left" if delta > 0 else "turn_right"
                message = "왼쪽으로 90도 돌아가세요." if delta > 0 else "오른쪽으로 90도 돌아가세요."
            else:
                # An arbitrary initial helmet yaw is not a 90-degree turn.
                action = "align_left" if delta > 0 else "align_right"
                message = "왼쪽으로 돌아 경로 방향을 맞추세요." if delta > 0 else "오른쪽으로 돌아 경로 방향을 맞추세요."
            approach = route.get("wall_approach")
            if action == "forward" and approach and math.hypot(origin["x"]-approach["x"], origin["y"]-approach["y"]) > .5:
                if abs(origin["x"]-approach["x"]) <= .1 or abs(origin["y"]-approach["y"]) <= .1:
                    message = "앞쪽 벽면을 향해 가세요."
            route.update(target=target, target_distance_m=round(distance, 2),
                         heading_deg=heading["heading_deg"], target_bearing_deg=round(bearing, 1),
                         relative_angle_deg=round(delta, 1))
    # A brief head turn must not immediately produce another spoken instruction.
    if state.get("candidate") != action:
        state.update(candidate=action, candidate_at=started)
    stable = started - state.get("candidate_at", started) >= 1.0
    if action == "announce":
        stable = True
    if action in {"location_stale", "heading_stale", "map_unverified", "no_route"}:
        stable = True
        route["available"] = False
        route["path"] = []
    route.update(action=action, message=message, instructions=[message],
                 navigation_enabled=True, instruction_stable=stable,
                 location_age_ms=round(location_age * 1000) if math.isfinite(location_age) else None,
                 heading_age_ms=round(heading_age * 1000) if math.isfinite(heading_age) else None,
                 updated_at=datetime.now(timezone.utc).isoformat(),
                 compute_ms=round((time.monotonic() - started) * 1000, 2))
    _latest[worker.worker_id] = route
    return device.device_id if device else None, route


def collect():
    result = []
    active_keys, active_workers = set(), set()
    with SessionLocal() as db:
        incidents = db.query(EvacuationIncident).filter(EvacuationIncident.status.in_(("active", "pending_manager"))).all()
        sites = set()
        for incident in sorted(incidents, key=lambda i: i.created_at, reverse=True):
            if incident.site_id in sites:
                continue
            sites.add(incident.site_id)
            if not json.loads(incident.details_json or "{}").get("navigation_enabled"):
                continue
            signature = map_signature(db, incident.site_id)
            routes, devices = {}, {}
            for worker in db.query(WorkerState).filter(WorkerState.site_id == incident.site_id).all():
                active_keys.add(f"{incident.incident_id}:{worker.worker_id}")
                active_workers.add(worker.worker_id)
                devices[worker.worker_id], routes[worker.worker_id] = navigation_step(db, worker, incident, signature)
            result.append((incident_to_dict(incident), routes, devices))
    for key in list(_state):
        if key not in active_keys:
            _state.pop(key, None)
    for key in list(_latest):
        if key not in active_workers:
            _latest.pop(key, None)
    return result


def stop_navigation_incident(incident_id):
    for worker_id, (key, task) in list(_pending.items()):
        if key[0] == incident_id:
            task.cancel()
            _pending.pop(worker_id, None)
            _latest.pop(worker_id, None)
    for key in list(_state):
        if key.startswith(incident_id + ":"):
            _state.pop(key, None)


async def run_navigation():
    pending = _pending
    try:
        while True:
            tick = time.monotonic()
            try:
                batches = await asyncio.to_thread(collect)
                valid = set()
                for incident, routes, devices in batches:
                    await manager.broadcast("evacuation_navigation", {"incident": incident, "routes": routes}, site_id=incident["site_id"])
                    for worker_id, route in routes.items():
                        valid.add(worker_id)
                        job = pending.get(worker_id)
                        # Drop an obsolete synthesis before delivery; never build a FIFO of turns.
                        key = (incident["incident_id"], route["action"])
                        if job and job[0] != key:
                            job[1].cancel()
                            pending.pop(worker_id, None)
                            job = None
                        if route["instruction_stable"] and (not job or job[1].done()):
                            task = asyncio.create_task(deliver(worker_id, devices[worker_id], incident["incident_id"], route))
                            pending[worker_id] = (key, task)
                        await asyncio.to_thread(_log.append, {"incident_id": incident["incident_id"], **route})
                for worker_id in list(pending):
                    if worker_id not in valid:
                        pending.pop(worker_id)[1].cancel()
            except Exception:
                logging.exception("Evacuation navigation tick failed")
            await asyncio.sleep(max(.05, .5 - (time.monotonic() - tick)))
    finally:
        for _, task in pending.values():
            task.cancel()
        await asyncio.gather(*(task for _, task in pending.values()), return_exceptions=True)
        clear_navigation()


async def deliver(worker_id, device_id, incident_id, route):
    started = time.monotonic()
    try:
        result = await send_helmet_guidance(worker_id, device_id, incident_id, route)
        if result.get("reason") != "throttled":
            await asyncio.to_thread(_log.append, {"event": "delivery", "worker_id": worker_id,
                "incident_id": incident_id, "action": route["action"], "result": result,
                "delivery_ms": round((time.monotonic() - started) * 1000, 2)})
    except asyncio.CancelledError:
        raise
    except Exception:
        logging.exception("Evacuation voice delivery failed")
