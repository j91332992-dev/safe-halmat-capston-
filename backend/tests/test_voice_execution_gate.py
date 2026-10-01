from app.config import settings
from app.services.voice_execution_gate import VoiceExecutionGate


def test_second_ordinary_command_in_same_capture_window_is_blocked(monkeypatch):
    monkeypatch.setattr(settings, "voice_command_cooldown_seconds", 3.0)
    gate = VoiceExecutionGate()

    assert gate.allow("helmet-test", "관리자에게 전화 연결해 줘") == (True, "accepted")
    assert gate.allow("helmet-test", "현재 위치 알려줘") == (False, "overlapping_command")


def test_safety_command_bypasses_other_command_but_duplicate_is_blocked(monkeypatch):
    monkeypatch.setattr(settings, "voice_command_cooldown_seconds", 3.0)
    gate = VoiceExecutionGate()

    assert gate.allow("helmet-test", "현재 위치 알려줘") == (True, "accepted")
    assert gate.allow("helmet-test", "화재 발생") == (True, "accepted")
    assert gate.allow("helmet-test", "화재 발생") == (False, "duplicate_command")
