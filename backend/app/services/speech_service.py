import re


COMMANDS = {
    "call_manager": ["관리자호출", "관리자연결", "관리자전화연결", "관리자불러줘", "전화연결", "통화연결", "전화해줘", "관니자호출"],
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


def normalize(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", text).lower()


def resolve_intent(text: str) -> tuple[str, float]:
    normalized = normalize(text)
    if normalized.endswith("전화연결") or normalized.endswith("통화연결"):
        return "call_manager", 0.96
    if normalized in LIFE_CRITICAL:
        return LIFE_CRITICAL[normalized], 1.0
    for intent, samples in COMMANDS.items():
        if any(sample in normalized or normalized in sample for sample in samples):
            return intent, 0.96
    try:
        from rapidfuzz import fuzz

        best = ("unknown", 0.0)
        for intent, samples in COMMANDS.items():
            if intent in {"emergency", "fire_report"}:
                continue
            score = max(fuzz.ratio(normalized, sample) for sample in samples) / 100
            if score > best[1]:
                best = (intent, score)
        return best if best[1] >= 0.55 else ("unknown", best[1])
    except ImportError:
        return "unknown", 0.0




