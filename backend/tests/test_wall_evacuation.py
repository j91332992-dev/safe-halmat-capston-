import asyncio
import importlib
import json
import math
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models.entities import (Device, EvacuationIncident, EvacuationNavigationPolicy,
                                 Obstacle, SiteLayout, WorkerState)
from app.services.evacuation_service import activate_voice_fire, calculate_route, _blocked
from app.services.evacuation_navigation import map_signature, navigation_step, clear_navigation
from app.services.safety_agent_service import build_safety_action_plan
from app.services.speech_service import resolve_intent
from app.services.wake_word_service import WakeWordGate


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(SiteLayout(site_id="s", width=5.2, height=3.6))
        db.add(WorkerState(worker_id="w", site_id="s", helmet_id="h", x=2.6, y=1.6,
                           last_valid_location_at=datetime.utcnow()))
        db.add(Obstacle(obstacle_id="exit", site_id="s", name="출구", object_type="emergency_exit",
                        x=4.8, y=3.2, width=.4, height=.4))
        db.add(Obstacle(obstacle_id="table", site_id="s", name="책상", object_type="obstacle",
                        x=1., y=.4, width=2.4, height=.6))
        db.flush()
        yield db
    clear_navigation()
    engine.dispose()


@pytest.mark.parametrize("text", ["화재 확정", "화재확정해", "화재가 맞아"])
def test_confirmation_bypasses_wake_and_does_not_auto_dial(text):
    assert resolve_intent(text)[0] == "fire_confirm"
    assert WakeWordGate().evaluate("av", text).status == "command"
    assert not build_safety_action_plan("fire_confirm", {}, text)["start_manager_call"]
    assert not build_safety_action_plan("fire_report", {}, "불이야")["start_manager_call"]
    assert build_safety_action_plan("call_manager", {}, "관리자 연결")["start_manager_call"]


@pytest.mark.parametrize("text", ["화재 확정하지 마", "화재 확정이라는 말을 설명해줘"])
def test_confirmation_requires_an_explicit_command(text):
    assert resolve_intent(text)[0] != "fire_confirm"


def test_voice_confirmation_uses_preverified_map_without_web_click(db):
    db.add(EvacuationNavigationPolicy(site_id="s", enabled=True, map_signature=map_signature(db, "s")))
    db.flush()
    incident, created = activate_voice_fire(db, "w", "화재 확정", True)
    assert created and incident.status == "active"
    assert json.loads(incident.details_json)["navigation_enabled"]
    assert json.loads(incident.fire_zone_json or "{}") == {}  # no invented fire location
    again, created = activate_voice_fire(db, "w", "화재 확정", True)
    assert again.incident_id == incident.incident_id and not created


def test_changed_map_does_not_silently_self_verify(db):
    db.add(EvacuationNavigationPolicy(site_id="s", enabled=True, map_signature="old-layout"))
    db.flush()
    incident, _ = activate_voice_fire(db, "w", "화재 확정", True)
    assert not json.loads(incident.details_json)["navigation_enabled"]


def test_wall_route_has_only_right_angle_vertices_and_physical_distance(db):
    worker = db.get(WorkerState, "w")
    route = calculate_route(db, worker)
    assert route["available"] and route["planning"]["style"] == "wall_first_orthogonal"
    objects = db.query(Obstacle).all()
    path = route["path"]
    assert len(path) >= 3
    length = 0.
    for a, b in zip(path, path[1:]):
        dx, dy = b["x"]-a["x"], b["y"]-a["y"]
        assert abs(dx) < 1e-8 or abs(dy) < 1e-8
        length += math.hypot(dx, dy)
        for i in range(101):
            assert not _blocked(a["x"]+dx*i/100, a["y"]+dy*i/100, objects, None)
    for a, b, c in zip(path,path[1:],path[2:]):
        assert (b["x"]-a["x"])*(c["x"]-b["x"]) + (b["y"]-a["y"])*(c["y"]-b["y"]) == pytest.approx(0.)
    assert route["distance_m"] == pytest.approx(length, abs=.011)
    assert route["planning"]["wall_lane_fraction"] > .4


def test_fire_blocks_the_only_exit(db):
    incident = EvacuationIncident(incident_id="f", site_id="s", source="test", status="active",
        fire_zone_json=json.dumps({"x":4.5,"y":2.9,"width":.7,"height":.7}))
    db.add(incident); db.flush()
    assert not calculate_route(db, db.get(WorkerState, "w"), incident)["available"]


def test_initial_instruction_has_no_seven_second_announcement_delay(db, monkeypatch):
    nav = importlib.import_module("app.services.evacuation_navigation")
    db.add(Device(device_id="av", site_id="s", worker_id="w", device_type="assistant_device"))
    incident = EvacuationIncident(incident_id="f", site_id="s", source="voice", status="active",
        details_json=json.dumps({"navigation_map_signature":map_signature(db,"s"), "navigation_enabled":True}))
    db.add(incident); db.flush()
    monkeypatch.setattr(nav, "device_to_dict", lambda d: {"heading_deg":0.,"heading_at":datetime.utcnow()})
    _, route = navigation_step(db, db.get(WorkerState,"w"), incident, map_signature(db,"s"))
    assert route["available"] and route["action"] != "announce"
    assert "도세요" not in route["message"] and "돌려" not in route["message"]


def test_corridor_keeps_corner_instead_of_diagonal_cut(db):
    from app.services.evacuation_corridor import follow_corridor
    path = [{"x":.6,"y":1.6},{"x":4.4,"y":1.6},{"x":4.4,"y":3.2}]
    state = {"corridor_path":path,"exit_id":"exit"}
    route = follow_corridor({"path":path,"exit_id":"exit"}, state,
        {"x":4.3,"y":1.6},[],None,5.2,3.6)
    for a,b in zip(route["path"],route["path"][1:]):
        assert abs(a["x"]-b["x"]) < 1e-8 or abs(a["y"]-b["y"]) < 1e-8


def test_missed_call_does_not_speak_or_end_fire(monkeypatch):
    from app.database import init_database, SessionLocal
    from app.models.entities import Event, CommandRecord
    from app.config import settings
    from app.websocket.call_manager import CallConnectionManager
    module = importlib.import_module("app.websocket.call_manager")
    guidance = importlib.import_module("app.services.evacuation_guidance_service")
    init_database()
    with SessionLocal() as db:
        db.add(Event(event_id="fire-call-test",event_type="VOICE_COMMAND",message="test",
                     device_id="helmet-001-av",worker_id="worker-001",details_json="{}"))
        db.commit()
    sent, notices = [], []
    async def send(device, command): sent.append(command); return 1
    async def broadcast(event, data): notices.append(event)
    async def tts(message): raise AssertionError("missed-call TTS must not run during evacuation")
    monkeypatch.setattr(settings,"call_answer_timeout_seconds",.01)
    monkeypatch.setattr(guidance,"evacuation_voice_active",lambda d:True)
    monkeypatch.setattr(module,"generate_tts",tts)
    monkeypatch.setattr(module.manager,"send_device_command",send)
    monkeypatch.setattr(module.manager,"broadcast",broadcast)
    async def scenario():
        manager = CallConnectionManager()
        await manager.begin_call_request("helmet-001-av","worker-001","fire-call-test")
        await asyncio.wait_for(manager.pending_requests["helmet-001-av"].timeout_task, timeout=2)
        assert not manager.pending_requests
    asyncio.run(scenario())
    assert "missed_call" in notices
    assert all(c["command_type"] not in {"play_audio","play_tone","stop_evacuation"} for c in sent)
    with SessionLocal() as db:
        assert not db.query(CommandRecord).filter(CommandRecord.payload_json.contains("call_no_answer")).all()


def test_voice_processing_delivers_first_route_without_call_or_generic_tts(monkeypatch):
    from app.database import SessionLocal, init_database
    from app.routers import audio
    from app.websocket import call_manager
    nav = importlib.import_module("app.services.evacuation_navigation")
    guidance = importlib.import_module("app.services.evacuation_guidance_service")
    init_database()
    sent = []
    async def first_route(worker, device, incident, route, **kwargs):
        sent.append(route)
        return {"sent":True,"message":route["message"]}
    async def unexpected(*args, **kwargs):
        raise AssertionError("fire routing must not use generic TTS or automatic phone dialing")
    monkeypatch.setattr(guidance,"send_helmet_guidance",first_route)
    monkeypatch.setattr(audio,"generate_tts",unexpected)
    monkeypatch.setattr(call_manager,"begin_call_request",unexpected)
    monkeypatch.setattr(nav,"device_to_dict",lambda d:{"heading_deg":0.,"heading_at":datetime.utcnow()})
    with SessionLocal() as db:
        db.add(SiteLayout(site_id="voice-route",width=5.2,height=3.6))
        db.add(WorkerState(worker_id="voice-route-worker",site_id="voice-route",helmet_id="voice-route-helmet",
                           x=2.4,y=1.6,last_valid_location_at=datetime.utcnow()))
        db.add(Device(device_id="voice-route-av",worker_id="voice-route-worker",site_id="voice-route",
                      device_type="assistant_device",online=True,last_seen=datetime.utcnow()))
        db.add(Obstacle(obstacle_id="voice-route-exit",site_id="voice-route",object_type="emergency_exit",
                        name="출구",x=4.8,y=3.2,width=.4,height=.4))
        db.flush()
        db.add(EvacuationNavigationPolicy(site_id="voice-route",enabled=True,
                                          map_signature=map_signature(db,"voice-route")))
        db.commit()
        result = asyncio.run(audio.process_text(db,"voice-route-worker","voice-route-av","화재 확정"))
        assert result["intent"] == "fire_confirm" and result["delivered_connections"] == 1
        assert not result["safety_agent"]["start_manager_call"]
        assert sent and sent[0]["available"] and sent[0]["action"] != "announce"
        assert result["evacuation"]["incident"]["status"] == "active"
