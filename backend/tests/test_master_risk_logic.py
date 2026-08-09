import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.entities import WorkerState, Zone
from app.services import risk_service
from app.services.risk_service import evaluate_risk
from app.services.speech_service import resolve_intent


def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def worker(**changes):
    values = {
        "worker_id": "worker-test",
        "worker_name": "테스트",
        "worker_role": "general_worker",
        "helmet_id": "helmet-test",
        "confidence": 0.9,
        "ppe_json": json.dumps({"helmet": True, "vest": True, "glove": True}),
        "hazard_json": "{}",
    }
    values.update(changes)
    return WorkerState(**values)


def test_priority_one_suppresses_lower_ppe_warning():
    db = session()
    item = worker(emergency=True, ppe_json=json.dumps({"helmet": False}))
    db.add(item)
    db.flush()
    result = evaluate_risk(db, item)
    assert result["priority"] == 1
    assert result["code"] == "LIFE_EMERGENCY"


def test_large_fire_threshold_is_priority_one():
    db = session()
    item = worker(hazard_json=json.dumps({"fire": True, "fire_area_ratio": 0.16}))
    db.add(item)
    db.flush()
    assert evaluate_risk(db, item)["code"] == "LARGE_FIRE"


def test_authorized_hot_work_is_bypassed_in_allowed_area(monkeypatch):
    db = session()
    monkeypatch.setattr(risk_service, "_night", lambda: False)
    item = worker(worker_role="hot_work_authorized", hazard_json=json.dumps({"fire": True, "fire_area_ratio": 0.02}))
    db.add(item)
    db.flush()
    result = evaluate_risk(db, item)
    assert result["code"] == "AUTHORIZED_HOT_WORK"
    assert result["points"] == 0


def test_controlled_zone_beats_ppe_warning():
    db = session()
    zone = Zone(
        zone_id="controlled",
        zone_name="통제구역",
        zone_type="rectangle",
        zone_category="controlled",
        coordinates_json="{}",
        allowed_worker_ids_json="[]",
    )
    item = worker(current_zone="controlled", ppe_json=json.dumps({"helmet": False}))
    db.add_all([zone, item])
    db.flush()
    result = evaluate_risk(db, item)
    assert result["priority"] == 3
    assert result["code"] == "ZONE_ACCESS_VIOLATION"


def test_emergency_keyword_requires_exact_full_phrase():
    assert resolve_intent("비상상황") == ("emergency", 1.0)
    assert resolve_intent("살려주세요") == ("emergency", 1.0)
    assert resolve_intent("비상금 이야기") [0] != "emergency"

def test_manager_call_intent_accepts_name_prefix():
    assert resolve_intent("관리자 연결") == ("call_manager", 0.96)
    assert resolve_intent("김민우 전화 연결") == ("call_manager", 0.96)
    assert resolve_intent("전화 연결") == ("call_manager", 0.96)


def test_manager_call_intent_accepts_semantic_variants():
    for phrase in (
        "팀장에게 연결해 줘",
        "팀장에게 전화 연결해 주세요",
        "팀장에게 연락해 줘",
        "현장 소장님과 통화하고 싶어",
        "관제실로 이어 줘",
        "안전 관리자 불러 주세요",
    ):
        intent, confidence = resolve_intent(phrase)
        assert intent == "call_manager"
        assert confidence >= 0.96


def test_unrelated_contact_sentence_is_not_manager_call():
    assert resolve_intent("집에 연락해 줘")[0] != "call_manager"


def test_supported_queries_accept_semantic_variants():
    examples = {
        "지금 위험 상태가 어떤지 알려 줘": "risk_query",
        "내가 있는 위치가 어디야": "location_query",
        "내 현재 상태를 확인해 줘": "status_report",
        "가까운 비상구가 어디인지 안내해 줘": "evacuation_route",
        "아까 경고를 한 번 더 말해 줘": "repeat_warning",
    }
    for phrase, expected in examples.items():
        intent, confidence = resolve_intent(phrase)
        assert intent == expected
        assert confidence >= 0.96
