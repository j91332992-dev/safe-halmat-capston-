import asyncio
import pytest
from app.services.assistant_service import build_response_smart, is_explanation_request

@pytest.mark.parametrize("text", ["비슷하네.", "일단 투투스 5초까지 한 2초 정도 올리고", "", "안녕하세요"])
def test_ambient_unknown_does_not_call_llm(text, monkeypatch):
    import openai
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("LLM must not be created for unclear speech")
    monkeypatch.setattr(openai, "AsyncOpenAI", forbidden)
    assert not is_explanation_request(text)
    result = asyncio.run(build_response_smart("unknown", {"emergency": True, "risk_level": "비상"}, text))
    assert calls == []
    assert result[0] == "다시 한 번 말씀해 주세요."

@pytest.mark.parametrize("text", ["현재 위험요소를 정리해줘", "지금 어떻게 해야 해", "작업자 상태를 설명해줘"])
def test_explicit_explanation_can_use_llm(text):
    assert is_explanation_request(text)
