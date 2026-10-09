import asyncio
import pytest

from app.services.assistant_service import build_response, build_response_smart
from app.services.speech_service import resolve_intent


@pytest.mark.parametrize('text,intent', [
    ('배터리 몇 퍼센트야', 'battery_query'),
    ('배터리 상태', 'battery_query'),
    ('보호구 상태 알려줘', 'ppe_query'),
    ('장치 연결됐어', 'device_query'),
    ('화재 발생 상태 알려줘', 'fire_report'),
    ('살려주세요 관리자 연결해줘', 'emergency'),
])
def test_fast_and_emergency_intents(text, intent):
    assert resolve_intent(text)[0] == intent


def test_stale_location_is_not_presented_as_live():
    message, _ = build_response('location_query', {'x': 2, 'y': 2, 'data_freshness': {'location': False}})
    assert '확인 불가' in message


def test_battery_is_exact_or_unknown():
    assert '72퍼센트' in build_response('battery_query', {'battery': 72})[0]
    assert '확인 불가' in build_response('battery_query', {})[0]


def test_offline_explanation_does_not_claim_safe_work():
    message, _ = asyncio.run(build_response_smart('unknown', {
        'ppe': {'vest': True}, 'risk_level': '정상',
        'data_freshness': {'location': False, 'vision': False},
    }, '현재 상황을 설명해줘'))
    assert '확인 불가' in message
