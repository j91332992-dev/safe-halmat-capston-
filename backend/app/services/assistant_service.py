import logging

from ..config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """당신은 스마트 안전모의 한국어 안전 AI '세이피'입니다.
작업자의 현재 위치, 위험도, 보호구와 감지 위험을 근거로 답하세요.
항상 정중하고 명확한 한국어로 2문장 이내로 답하세요.
비상 또는 도움 요청이면 즉시 관제실 전송 사실과 안전한 대피를 강조하세요.
제공되지 않은 사실이나 센서 값을 만들어내지 마세요."""


def build_response(intent: str, worker: dict) -> tuple[str, str | None]:
    responses = {
        "call_manager": ("관리자에게 호출을 전송했습니다.", "play_tone"),
        "status_report": (f"현재 상태는 {worker.get('risk_level', '알 수 없음')}입니다.", "play_tone"),
        "location_query": (f"현재 위치는 X {worker.get('x', 0):.1f}, Y {worker.get('y', 0):.1f} 미터입니다.", "play_tone"),
        "risk_query": (f"현재 위험도는 {worker.get('risk_score', 0)}점, {worker.get('risk_level', '알 수 없음')} 단계입니다.", "play_tone"),
        "help": ("도움 요청을 관제실에 전송했습니다. 안전한 장소에서 대기하세요.", "play_alert"),
        "emergency": ("비상 신고를 접수했습니다. 즉시 위험 장소에서 대피하세요.", "play_alert"),
        "repeat_warning": ("최근 경고를 다시 재생합니다.", "play_alert"),
    }
    return responses.get(intent, ("명령을 이해하지 못했습니다. 다시 말씀해 주세요.", None))


async def build_response_smart(intent: str, worker: dict) -> tuple[str, str | None]:
    fallback = build_response(intent, worker)
    if not settings.use_gpt_response or not settings.openai_api_key:
        return fallback
    try:
        from openai import AsyncOpenAI

        ppe = worker.get("ppe", {})
        hazards = worker.get("hazards", {})
        context = (
            f"의도: {intent}\n"
            f"위치: X {worker.get('x', 0):.1f}, Y {worker.get('y', 0):.1f} m\n"
            f"위험도: {worker.get('risk_score', 0)}점 / {worker.get('risk_level', '알 수 없음')}\n"
            f"보호구: {ppe}\n감지 위험: {hazards}\n"
            "위 정보만 사용해 작업자에게 바로 말할 응답을 작성하세요."
        )
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.responses.create(
            model=settings.gpt_model,
            instructions=SYSTEM_PROMPT,
            input=context,
            max_output_tokens=settings.gpt_max_output_tokens,
        )
        message = (response.output_text or "").strip()
        if not message:
            return fallback
        speaker_command = "play_alert" if intent in {"emergency", "help", "repeat_warning"} else "play_tone"
        return message, speaker_command
    except Exception as exc:
        logger.warning("OpenAI 응답 생성 실패, 고정 응답 사용: %s", exc)
        return fallback