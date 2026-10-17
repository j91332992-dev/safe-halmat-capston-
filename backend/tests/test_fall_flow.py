import asyncio
from datetime import datetime, timedelta
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.entities import Device, Event, FallIncident, WorkerState
from app.routers import falls
from app.routers.events import change_status
from app.services import fall_service as flow


@pytest.fixture
def fall_db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    published = []

    async def broadcast(kind, data, site_id=None):
        published.append((kind, data, site_id))

    async def tts(_text):
        return Path("fall.wav")

    monkeypatch.setattr(flow.manager, "broadcast", broadcast)
    monkeypatch.setattr(flow, "generate_tts", tts)
    monkeypatch.setattr(flow, "SessionLocal", factory)
    monkeypatch.setattr(flow, "launch", lambda coroutine: coroutine.close())
    monkeypatch.setattr(settings, "call_device_token", "fall-test-token")
    with factory() as db:
        db.add(WorkerState(worker_id="fall-worker", helmet_id="fall-helmet", site_id="fall-site"))
        db.add(Device(device_id="fall-device", device_type="assistant_device", worker_id="fall-worker", site_id="fall-site"))
        db.add(WorkerState(worker_id="other-worker", helmet_id="other-helmet", site_id="other-site"))
        db.add(Device(device_id="other-device", device_type="assistant_device", worker_id="other-worker", site_id="other-site"))
        db.commit()
    def override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override
    yield factory, published
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def detect(db, detection_id="boot-1"):
    return asyncio.run(flow.detect(db, db.get(Device, "fall-device"), detection_id,
                                   {"peak_g": 3, "peak_rad_s": 3, "tilt_deg": 70}))


def test_initial_notice_before_prompt_and_eight_seconds_after_playback(fall_db, monkeypatch):
    factory, published = fall_db
    clock = [datetime(2026, 10, 17, 0, 0, 0)]
    monkeypatch.setattr(flow, "utcnow", lambda: clock[0])
    with factory() as db:
        incident = detect(db)
        assert incident.state == "waiting_prompt"
        assert published[0][1]["message"] == "낙상 의심 감지, 응답 확인 중…"
        assert published[0][2] == "fall-site"
        clock[0] += timedelta(seconds=12)
        asyncio.run(flow.playback(db, incident, True, 8000))
        assert incident.deadline == clock[0] + timedelta(seconds=8)
        clock[0] += timedelta(seconds=7.99)
        asyncio.run(flow.expire(db))
        assert incident.state == "waiting_response"
        clock[0] += timedelta(seconds=.01)
        asyncio.run(flow.expire(db))
        assert incident.state == "emergency"
        assert db.get(Event, incident.incident_id).message == flow.ADMIN["unavailable"]
        assert published[-1][1]["notify"] is True


@pytest.mark.parametrize("text, outcome", [("괜찮습니다.", "safe"), ("도와주세요!", "help")])
def test_explicit_reply_updates_same_event_and_retains_history(fall_db, text, outcome):
    factory, published = fall_db
    with factory() as db:
        incident = detect(db)
        asyncio.run(flow.playback(db, incident, True, 8000))
        asyncio.run(flow.finish(db, incident, flow.classify(text), "explicit_response", text))
        event = db.get(Event, incident.incident_id)
        assert db.query(Event).count() == 1
        assert event.message == flow.ADMIN[outcome]
        assert len(json.loads(event.details_json)["history"]) == 3
        assert incident.state == ("cleared" if outcome == "safe" else "emergency")
        assert published[-1][1]["notify"] == (outcome == "help")
        assert json.loads(event.details_json)["wearer_message"] == flow.WEARER[outcome]
        assert not db.get(WorkerState, "fall-worker").emergency
        asyncio.run(flow.finish(db, incident, "unavailable", "late_timeout"))
        assert event.message == flow.ADMIN[outcome]


@pytest.mark.parametrize("text", ["", "네", "응", "아니요", "괜찮지 않습니다", "안 괜찮습니다",
                                   "괜찮습니다 도와주세요", "저는 괜찮습니다", "살려주세요", "구해주세요",
                                   "구조 요청합니다", "도움이 필요합니다", flow.PROMPT, settings.stt_command_prompt])
def test_ambiguous_negated_and_prompt_echo_are_not_safe(text):
    assert flow.classify(text) is None


def test_duplicate_and_additional_detection_do_not_restart_timer(fall_db):
    factory, published = fall_db
    with factory() as db:
        incident = detect(db)
        asyncio.run(flow.playback(db, incident, True, 3000))
        deadline = incident.deadline
        assert detect(db).incident_id == incident.incident_id
        assert detect(db, "boot-2").incident_id == incident.incident_id
        assert incident.deadline == deadline
        asyncio.run(flow.finish(db, incident, "safe", "explicit_response"))
        assert detect(db, "boot-2").incident_id == incident.incident_id
        assert db.query(Event).count() == 1


def test_missing_prompt_ack_escalates_and_playback_failure_does_not_open_listening(fall_db):
    factory, _ = fall_db
    with factory() as db:
        incident = detect(db)
        asyncio.run(flow.playback(db, incident, False, 8000))
        assert incident.state == "emergency"
        assert json.loads(db.get(Event, incident.incident_id).details_json)["history"][-1]["reason"] == "prompt_playback_failed"


def test_tts_preparation_and_failure(fall_db, monkeypatch):
    factory, _ = fall_db
    with factory() as db:
        incident = detect(db)
        incident_id = incident.incident_id
    asyncio.run(flow.prepare_audio(incident_id, True))
    with factory() as db:
        assert db.get(FallIncident, incident_id).prompt_url == "/tts/fall.wav"
    async def failed(_text):
        return None
    monkeypatch.setattr(flow, "generate_tts", failed)
    asyncio.run(flow.prepare_audio(incident_id, True))
    with factory() as db:
        assert db.get(FallIncident, incident_id).state == "emergency"
    asyncio.run(flow.prepare_audio(incident_id, False))
    with factory() as db:
        assert db.get(FallIncident, incident_id).result_ready is True


def test_api_auth_call_ignore_and_device_binding(fall_db):
    factory, _ = fall_db
    client = TestClient(app)
    body = {"device_id": "fall-device", "detection_id": "abc", "peak_g": 3, "peak_rad_s": 3, "tilt_deg": 70}
    headers = {"Authorization": "Bearer fall-test-token"}
    assert client.post("/api/falls/detect", json=body).status_code == 401
    result = client.post("/api/falls/detect", json={**body, "call_active": True}, headers=headers)
    assert result.json() == {"ignored": True, "reason": "call_active"}
    with factory() as db:
        assert db.query(Event).count() == 0
    result = client.post("/api/falls/detect", json=body, headers=headers)
    incident_id = result.json()["incident_id"]
    assert client.get(f"/api/falls/{incident_id}?device_id=other-device", headers=headers).status_code == 404
    assert client.post(f"/api/falls/{incident_id}/playback", json={"device_id": "fall-device", "ok": True}, headers=headers).json()["state"] == "waiting_response"


@pytest.mark.parametrize("text, state", [("네", "waiting_response"), ("괜찮습니다", "cleared"),
                                        ("도와주세요", "emergency"), ("", "waiting_response")])
def test_audio_reply_bypasses_wake_gate_only_for_bound_active_incident(fall_db, monkeypatch, text, state):
    factory, _ = fall_db
    async def fake_stt(_path, *, command_only=False):
        assert command_only is True
        return text
    monkeypatch.setattr(falls, "stt", fake_stt)
    with factory() as db:
        incident = detect(db)
        asyncio.run(flow.playback(db, incident, True, 8000))
        incident_id = incident.incident_id
    client = TestClient(app)
    result = client.post(f"/api/falls/{incident_id}/audio", headers={"Authorization": "Bearer fall-test-token"},
                         data={"device_id": "fall-device"}, files={"file": ("reply.wav", b"RIFFfake", "audio/wav")})
    assert result.status_code == 200
    assert result.json()["state"] == state


def test_prompt_timeout_survives_new_session(fall_db, monkeypatch):
    factory, _ = fall_db
    with factory() as db:
        incident = detect(db)
        incident_id = incident.incident_id
        expired_at = incident.deadline + timedelta(seconds=1)
    monkeypatch.setattr(flow, "utcnow", lambda: expired_at)
    with factory() as db:
        asyncio.run(flow.expire(db))
        assert db.get(FallIncident, incident_id).state == "emergency"


def test_speech_started_before_eight_seconds_can_finish_after_window(fall_db, monkeypatch):
    factory, _ = fall_db
    with factory() as db:
        incident = detect(db)
        asyncio.run(flow.playback(db, incident, True, 8000))
        incident_id = incident.incident_id
        deadline = incident.deadline
    clock = [deadline - timedelta(seconds=1)]
    monkeypatch.setattr(flow, "utcnow", lambda: clock[0])
    monkeypatch.setattr(falls, "utcnow", lambda: clock[0])
    client = TestClient(app)
    headers = {"Authorization": "Bearer fall-test-token"}
    payload = {"device_id": "fall-device", "ok": True}
    assert client.post(f"/api/falls/{incident_id}/speech-start", json=payload, headers=headers).status_code == 200
    with factory() as db:
        original_until = db.get(FallIncident, incident_id).stt_until
    clock[0] += timedelta(seconds=3)
    client.post(f"/api/falls/{incident_id}/speech-start", json=payload, headers=headers)
    with factory() as db:
        asyncio.run(flow.expire(db))
        assert db.get(FallIncident, incident_id).state == "waiting_response"
        assert db.get(FallIncident, incident_id).stt_until == original_until
    async def reply(_path, *, command_only=False):
        return "괜찮습니다"
    monkeypatch.setattr(falls, "stt", reply)
    result = client.post(f"/api/falls/{incident_id}/audio", headers=headers, data={"device_id": "fall-device"},
                         files={"file": ("reply.wav", b"RIFFfake", "audio/wav")})
    assert result.json()["state"] == "cleared"


def test_active_stt_gets_bounded_grace_and_empty_result_escalates(fall_db, monkeypatch):
    factory, _ = fall_db
    with factory() as db:
        incident = detect(db)
        asyncio.run(flow.playback(db, incident, True, 8000))
        incident_id, deadline = incident.incident_id, incident.deadline
    clock = [deadline - timedelta(seconds=1)]
    monkeypatch.setattr(flow, "utcnow", lambda: clock[0])
    monkeypatch.setattr(falls, "utcnow", lambda: clock[0])
    async def reply(_path, *, command_only=False):
        clock[0] += timedelta(seconds=2)
        with factory() as db:
            await flow.expire(db)
            assert db.get(FallIncident, incident_id).state == "waiting_response"
        return ""
    monkeypatch.setattr(falls, "stt", reply)
    result = TestClient(app).post(f"/api/falls/{incident_id}/audio", headers={"Authorization": "Bearer fall-test-token"},
        data={"device_id": "fall-device"}, files={"file": ("reply.wav", b"RIFFfake", "audio/wav")})
    assert result.json()["state"] == "emergency"


def test_safe_reply_does_not_clear_unrelated_emergency(fall_db):
    factory, _ = fall_db
    with factory() as db:
        worker = db.get(WorkerState, "fall-worker")
        worker.emergency = True
        worker.hazard_json = '{"fallen": true}'
        db.commit()
        incident = detect(db)
        asyncio.run(flow.playback(db, incident, True, 8000))
        asyncio.run(flow.finish(db, incident, "safe", "explicit_response"))
        assert worker.emergency is True
        assert json.loads(worker.hazard_json)["fallen"] is True


def test_manual_resolution_removes_only_fall_emergency(fall_db):
    factory, _ = fall_db
    with factory() as db:
        incident = detect(db)
        asyncio.run(flow.finish(db, incident, "help", "explicit_response"))
        worker = db.get(WorkerState, "fall-worker")
        assert json.loads(worker.hazard_json)["fall_emergency"] is True
        worker.emergency = True
        db.commit()
        asyncio.run(change_status(incident.incident_id, "resolved", "fall-site", db))
        assert "fall_emergency" not in json.loads(worker.hazard_json)
        assert worker.emergency is True


def test_live_call_on_server_ignores_new_detection(fall_db, monkeypatch):
    monkeypatch.setitem(falls.call_manager.operators, "fall-device", [object()])
    result = TestClient(app).post("/api/falls/detect", headers={"Authorization": "Bearer fall-test-token"},
        json={"device_id": "fall-device", "detection_id": "active-call", "peak_g": 3, "peak_rad_s": 3, "tilt_deg": 70})
    assert result.json()["ignored"] is True


def test_audio_can_confirm_lost_playback_ack_without_replaying_prompt(fall_db, monkeypatch):
    factory, _ = fall_db
    async def reply(_path, *, command_only=False):
        return "괜찮습니다"
    monkeypatch.setattr(falls, "stt", reply)
    with factory() as db:
        incident_id = detect(db).incident_id
    result = TestClient(app).post(f"/api/falls/{incident_id}/audio", headers={"Authorization": "Bearer fall-test-token"},
        data={"device_id": "fall-device", "playback_finished": "true", "remaining_ms": "6000"},
        files={"file": ("reply.wav", b"RIFFfake", "audio/wav")})
    assert result.json()["state"] == "cleared"


def test_playback_retransmission_does_not_extend_window(fall_db):
    factory, _ = fall_db
    with factory() as db:
        incident = detect(db)
        asyncio.run(flow.playback(db, incident, True, 2000))
        deadline = incident.deadline
        asyncio.run(flow.playback(db, incident, True, 8000))
        assert incident.deadline == deadline
