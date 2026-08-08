from app.config import settings
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