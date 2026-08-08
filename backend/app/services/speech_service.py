import re


COMMANDS = {
    "call_manager": ["관리자호출", "관리자불러줘", "관니자호출"],
    "status_report": ["상태보고", "상태알려줘"],
    "location_query": ["내위치", "내위치알려줘"],
    "risk_query": ["위험도", "현재위험도알려줘"],
    "help": ["도와줘", "도움요청"],
    "emergency": ["비상상황", "살려주세요"],
    "fire_report": ["화재발생", "불이났어요", "불났어요"],
    "repeat_warning": ["경고다시말해줘"],
    "evacuation_route": ["대피경로", "어디로대피", "비상구알려줘"],
}
LIFE_CRITICAL = {"비상상황": "emergency", "살려주세요": "emergency", "화재발생": "fire_report", "불이났어요": "fire_report", "불났어요": "fire_report"}


def normalize(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", text).lower()


def resolve_intent(text: str) -> tuple[str, float]:
    normalized = normalize(text)
    if normalized in LIFE_CRITICAL:
        return LIFE_CRITICAL[normalized], 1.0
    for intent, samples in COMMANDS.items():
        if intent in {"emergency", "fire_report"}:
            continue
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




