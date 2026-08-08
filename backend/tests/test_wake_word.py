from app.services.wake_word_service import WakeWordGate


def test_ordinary_conversation_is_ignored():
    gate = WakeWordGate()
    decision = gate.evaluate("helmet-test", "오늘 작업장 많이 덥네요")
    assert decision.status == "ignored"
    assert decision.reason == "wake_word_missing"


def test_wake_word_and_command_are_accepted():
    gate = WakeWordGate()
    decision = gate.evaluate("helmet-test", "세이피 현재 위험도 알려줘")
    assert decision.status == "command"
    assert decision.command_text == "현재위험도알려줘"


def test_wake_word_only_arms_one_followup():
    gate = WakeWordGate()
    armed = gate.evaluate("helmet-test", "세이피")
    followup = gate.evaluate("helmet-test", "현재 위치 알려줘")
    assert armed.status == "armed"
    assert followup.status == "command"
    assert followup.reason == "armed_followup"


def test_life_critical_phrase_bypasses_wake_word():
    gate = WakeWordGate()
    decision = gate.evaluate("helmet-test", "화재 발생")
    assert decision.status == "command"
    assert decision.reason == "life_critical_bypass"


def test_empty_stt_is_ignored():
    gate = WakeWordGate()
    decision = gate.evaluate("helmet-test", "")
    assert decision.status == "ignored"
    assert decision.reason == "stt_empty"
