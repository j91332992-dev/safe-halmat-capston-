from app.services.safety_agent_service import build_safety_action_plan
from app.services.speech_service import resolve_intent


def test_natural_life_safety_phrases_are_emergency_intents():
    assert resolve_intent("살려줘")[0] == "emergency"
    assert resolve_intent("기계에 손이 끼었어요")[0] == "emergency"
    assert resolve_intent("숨을 못 쉬겠어요")[0] == "emergency"


def test_emergency_plan_includes_sos_location_call_and_guidance():
    plan = build_safety_action_plan(
        "emergency",
        {"x": 2.4, "y": 5.1, "current_zone": "A구역", "confidence": 0.91, "risk_score": 90, "risk_level": "위험", "hazards": {"smoke": True}},
        "기계에 손이 끼었어요",
    )
    assert plan["mode"] == "emergency"
    assert plan["start_manager_call"] is True
    assert plan["location"]["x"] == 2.4
    assert plan["camera_context"] == "카메라 연기 감지"
    assert [action["type"] for action in plan["actions"]] == ["sos", "share_location", "manager_call", "voice_guidance"]
