import pytest
from app.services.speech_service import resolve_intent
from app.services.wake_word_service import WakeWordGate

@pytest.mark.parametrize("text", ["화재상황 발생", "화재 상황 발생!", "화재 상황이 발생했습니다", "화재 발생", "불이야"])
def test_fire_without_wake(text):
    assert resolve_intent(text)[0] == "fire_report"
    decision = WakeWordGate().evaluate("test",text)
    assert decision.status == "command"
    assert decision.reason == "life_critical_bypass"
