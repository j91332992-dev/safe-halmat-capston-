import re


COMMANDS = {
    "call_manager": [
        "관리자호출", "관리자연결", "관리자전화연결", "관리자불러줘",
        "팀장연결", "팀장전화연결", "팀장에게연락해줘", "팀장불러줘",
        "전화연결", "통화연결", "전화해줘", "관니자호출",
    ],
    "status_report": ["상태보고", "상태알려줘"],
    "location_query": ["내위치", "내위치알려줘"],
    "risk_query": ["위험도", "현재위험도알려줘"],
    "help": ["도와줘", "도와주세요", "도움요청", "도움이필요해요"],
    "emergency": ["비상상황", "비상상황입니다", "살려주세요", "긴급상황"],
    "fire_report": ["화재발생", "화재가발생", "화제발생", "불이났어요", "불이났습니다", "불났어요", "불났습니다"],
    "repeat_warning": ["경고다시말해줘"],
    "evacuation_route": ["대피경로", "어디로대피", "비상구알려줘"],
}
LIFE_CRITICAL = {sample: intent for intent in ("help", "emergency", "fire_report") for sample in COMMANDS[intent]}

CALL_TARGETS = (
    "관리자", "관니자", "팀장", "반장", "현장소장", "소장", "관제실",
    "안전관리자", "안전담당자", "책임자",
)
CALL_ACTIONS = (
    "연결", "전화", "통화", "연락", "호출", "불러", "이어줘", "바꿔줘",
)

STOP_SPEAKING_PHRASES = ("그만", "그만말해", "조용히", "멈춰", "말그만")
HANG_UP_PHRASES = (
    "끊어줘", "전화끊어", "통화종료", "통화끝", "그만통화",
    "전화중단", "통화중단", "연결중단", "중단",
)


def normalize(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", text).lower()


def resolve_intent(text: str) -> tuple[str, float]:
    normalized = normalize(text)
    if not normalized:
        return "unknown", 0.0
    if any(phrase in normalized for phrase in HANG_UP_PHRASES):
        return "hang_up", 1.0
    if any(phrase in normalized for phrase in STOP_SPEAKING_PHRASES):
        return "stop_speaking", 1.0
    if any(target in normalized for target in CALL_TARGETS) and any(
        action in normalized for action in CALL_ACTIONS
    ):
        return "call_manager", 0.96
    if normalized.endswith("전화연결") or normalized.endswith("통화연결"):
        return "call_manager", 0.96

    # 같은 의미를 여러 자연스러운 표현으로 말해도 동일한 기능으로 묶는다.
    if "위험" in normalized and any(word in normalized for word in ("알려", "어때", "확인", "상태", "점수")):
        return "risk_query", 0.97
    if "위치" in normalized and any(word in normalized for word in ("알려", "어디", "확인", "찾아")):
        return "location_query", 0.97
    if "상태" in normalized and any(word in normalized for word in ("알려", "보고", "확인", "어때")):
        return "status_report", 0.97
    if any(word in normalized for word in ("대피", "비상구", "탈출구")) and any(
        word in normalized for word in ("경로", "어디", "알려", "찾아", "안내")
    ):
        return "evacuation_route", 0.97
    if any(word in normalized for word in ("경고", "안내")) and any(
        word in normalized for word in ("다시", "반복", "한번더")
    ):
        return "repeat_warning", 0.97

    if normalized in LIFE_CRITICAL:
        return LIFE_CRITICAL[normalized], 1.0
    for intent, samples in COMMANDS.items():
        # Only match a complete known phrase inside the transcript. Reversing
        # this check made one-syllable STT noise such as "어" match "불이났어요".
        if any(sample in normalized for sample in samples):
            return intent, 0.96
    try:
        from rapidfuzz import fuzz

        best = ("unknown", 0.0)
        for intent, samples in COMMANDS.items():
            # 통화는 오작동 영향이 크므로 대상/명시 문구가 확인된 경우에만 실행한다.
            if intent in {"call_manager", "emergency", "fire_report"}:
                continue
            score = max(fuzz.ratio(normalized, sample) for sample in samples) / 100
            if score > best[1]:
                best = (intent, score)
        return best if best[1] >= 0.55 else ("unknown", best[1])
    except ImportError:
        return "unknown", 0.0




