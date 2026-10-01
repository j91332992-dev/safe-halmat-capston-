import asyncio
import importlib
import json
from uuid import uuid4

from app.config import settings
from app.database import SessionLocal, init_database
from app.models.entities import CommandRecord, Event
from app.websocket.call_manager import CallConnectionManager


def test_device_token_must_match(monkeypatch):
    monkeypatch.setattr(settings, "call_device_token", "device-secret")
    manager = CallConnectionManager()
    assert manager.valid_device_token("device-secret") is True
    assert manager.valid_device_token("wrong-secret") is False
    assert manager.valid_device_token("") is False


def test_operator_ticket_is_single_use():
    manager = CallConnectionManager()
    ticket = manager.issue_ticket("helmet-001-av")
    assert manager.consume_ticket("helmet-001-av", ticket) is True
    assert manager.consume_ticket("helmet-001-av", ticket) is False


def test_operator_ticket_is_bound_to_device():
    manager = CallConnectionManager()
    ticket = manager.issue_ticket("helmet-001-av")
    assert manager.consume_ticket("another-device", ticket) is False


def _create_call_request(event_id: str, device_id: str = "helmet-001-av") -> None:
    init_database()
    with SessionLocal() as db:
        db.add(Event(
            event_id=event_id,
            event_type="VOICE_COMMAND",
            severity="info",
            message="call request",
            worker_id="worker-001",
            device_id=device_id,
            details_json=json.dumps({"intent": "call_manager"}),
        ))
        db.commit()


def _delete_call_test_rows(event_id: str) -> None:
    with SessionLocal() as db:
        db.query(Event).filter(
            (Event.event_id == event_id) | (Event.details_json.contains(event_id))
        ).delete(synchronize_session=False)
        db.query(CommandRecord).filter(CommandRecord.payload_json.contains("call_no_answer")).delete(synchronize_session=False)
        db.commit()


def test_answering_cancels_pending_request(monkeypatch):
    event_id = str(uuid4())
    _create_call_request(event_id)
    call_module = importlib.import_module("app.websocket.call_manager")

    async def no_connections(*_args, **_kwargs):
        return 0

    monkeypatch.setattr(call_module.manager, "send_device_command", no_connections)
    monkeypatch.setattr(call_module.manager, "broadcast", no_connections)
    manager = CallConnectionManager()

    async def scenario():
        await manager.begin_call_request("helmet-001-av", "worker-001", event_id)
        assert "helmet-001-av" in manager.pending_requests
        assert await manager.cancel_call_request("helmet-001-av", reason="answered") is True
        assert "helmet-001-av" not in manager.pending_requests
        with SessionLocal() as db:
            answered = db.get(Event, event_id)
            assert answered.status == "acknowledged"
            assert json.loads(answered.details_json)["call_state"] == "answered"
        await manager._resolve_active_request("helmet-001-av")

    try:
        asyncio.run(scenario())
        with SessionLocal() as db:
            event = db.get(Event, event_id)
            assert event.status == "resolved"
            assert json.loads(event.details_json)["call_state"] == "ended"
    finally:
        _delete_call_test_rows(event_id)


def test_unanswered_request_creates_one_missed_call(monkeypatch):
    event_id = str(uuid4())
    _create_call_request(event_id)
    call_module = importlib.import_module("app.websocket.call_manager")

    async def no_audio(_message):
        return None

    async def no_connections(*_args, **_kwargs):
        return 0

    monkeypatch.setattr(settings, "call_answer_timeout_seconds", 0.01)
    monkeypatch.setattr(call_module, "generate_tts", no_audio)
    monkeypatch.setattr(call_module.manager, "send_device_command", no_connections)
    monkeypatch.setattr(call_module.manager, "broadcast", no_connections)
    manager = CallConnectionManager()

    async def scenario():
        await manager.begin_call_request("helmet-001-av", "worker-001", event_id)
        await asyncio.sleep(0.05)

    try:
        asyncio.run(scenario())
        with SessionLocal() as db:
            original = db.get(Event, event_id)
            missed = db.query(Event).filter(
                Event.event_type == "MISSED_CALL",
                Event.details_json.contains(event_id),
            ).all()
            assert original.status == "resolved"
            assert json.loads(original.details_json)["call_state"] == "missed"
            assert len(missed) == 1
            command = db.query(CommandRecord).filter(CommandRecord.payload_json.contains("call_no_answer")).one()
            assert command.command_type == "play_tone"
    finally:
        _delete_call_test_rows(event_id)


def test_spoken_hangup_cancels_request_while_ringing(monkeypatch):
    event_id = str(uuid4())
    _create_call_request(event_id)
    call_module = importlib.import_module("app.websocket.call_manager")

    async def no_connections(*_args, **_kwargs):
        return 0

    monkeypatch.setattr(call_module.manager, "send_device_command", no_connections)
    monkeypatch.setattr(call_module.manager, "broadcast", no_connections)
    manager = CallConnectionManager()

    async def scenario():
        await manager.begin_call_request("helmet-001-av", "worker-001", event_id)
        await manager.end_call("helmet-001-av")
        assert "helmet-001-av" not in manager.pending_requests

    try:
        asyncio.run(scenario())
        with SessionLocal() as db:
            event = db.get(Event, event_id)
            assert event.status == "resolved"
            assert json.loads(event.details_json)["call_state"] == "cancelled"
    finally:
        _delete_call_test_rows(event_id)
