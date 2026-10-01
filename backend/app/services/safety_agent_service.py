"""Turn safety voice intent plus live worker context into concrete actions.

This remains deliberately rule-first: a life-safety request must not wait for
an external LLM or network call before creating the SOS and call request.
"""

from typing import Any


EMERGENCY_INTENTS = {"help", "emergency", "fire_report"}


def build_safety_action_plan(intent: str, worker: dict[str, Any], text: str) -> dict[str, Any]:
    """Return an auditable plan for the operator UI and event log."""
    emergency = intent in EMERGENCY_INTENTS
    hazards = worker.get("hazards") or {}
    camera_state = "위험 감지 없음"
    if hazards.get("fire"):
        camera_state = "카메라 화재 감지"
    elif hazards.get("smoke"):
        camera_state = "카메라 연기 감지"
    elif hazards.get("observed_person_missing_ppe"):
        camera_state = "카메라 보호구 이상 감지"

    location = {
        "x": round(float(worker.get("x", 0)), 1),
        "y": round(float(worker.get("y", 0)), 1),
        "zone": worker.get("current_zone"),
        "confidence": worker.get("confidence"),
    }
    actions = []
    if emergency:
        actions = [
            {"type": "sos", "label": "SOS 관제 알림", "status": "requested"},
            {"type": "share_location", "label": "마지막 UWB 위치 전달", "status": "ready"},
            {"type": "manager_call", "label": "관리자 통화 요청", "status": "requested"},
            {"type": "voice_guidance", "label": "안전모 긴급 안내", "status": "requested"},
        ]
    elif intent == "call_manager":
        actions = [
            {"type": "manager_call", "label": "관리자 통화 요청", "status": "requested"},
            {"type": "share_location", "label": "현재 위치 전달", "status": "ready"},
        ]

    return {
        "mode": "emergency" if emergency else "assist",
        "source_text": text,
        "location": location,
        "risk": {"score": worker.get("risk_score", 0), "level": worker.get("risk_level", "정상")},
        "camera_context": camera_state,
        "actions": actions,
        "start_manager_call": emergency or intent == "call_manager",
    }
