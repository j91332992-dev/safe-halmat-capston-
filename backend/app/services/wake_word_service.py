from dataclasses import dataclass
from threading import Lock
from time import monotonic

from ..config import settings
from .speech_service import normalize, resolve_intent

STT_PROMPT_ECHO_MARKERS = (
    "산업안전모음성명령입니다",
    "호출어는투투스입니다",
    "긴급명령은화재발생",
    "한국어산업안전현장대화입니다",
    "들리지않는내용은추측하지마세요",
)


@dataclass(frozen=True)
class WakeDecision:
    status: str
    transcript: str
    command_text: str = ""
    reason: str = ""


class WakeWordGate:
    def __init__(self) -> None:
        self._armed_until: dict[str, float] = {}
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._armed_until.clear()

    def arm(self, device_id: str) -> None:
        """Allow one additional command after a retry prompt."""
        with self._lock:
            self._armed_until[device_id] = monotonic() + settings.wake_followup_seconds

    def evaluate(self, device_id: str, transcript: str) -> WakeDecision:
        text = (transcript or "").strip()
        normalized = normalize(text)
        if not normalized:
            now = monotonic()
            with self._lock:
                deadline = self._armed_until.get(device_id, 0.0)
                if deadline > now:
                    self._armed_until.pop(device_id, None)
                    return WakeDecision("command", text, "", "armed_followup_empty")
                self._armed_until.pop(device_id, None)
            return WakeDecision("ignored", text, reason="stt_empty")

        if any(marker in normalized for marker in STT_PROMPT_ECHO_MARKERS):
            return WakeDecision("ignored", text, reason="stt_prompt_echo")

        # 생명안전 명령은 웨이크워드 없이도 즉시 처리한다.
        intent, confidence = resolve_intent(text)
        if intent in {"emergency", "help", "fire_report"} and confidence >= 0.75:
            with self._lock:
                self._armed_until.pop(device_id, None)
            return WakeDecision("command", text, text, "life_critical_bypass")

        aliases = sorted(
            {normalize(item) for item in settings.wake_word_alias_list if normalize(item)},
            key=len,
            reverse=True,
        )
        for alias in aliases:
            if not normalized.startswith(alias):
                continue
            command = normalized[len(alias):]
            with self._lock:
                if command:
                    self._armed_until.pop(device_id, None)
                else:
                    self._armed_until[device_id] = monotonic() + settings.wake_followup_seconds
            if command:
                return WakeDecision("command", text, command, "wake_word_with_command")
            return WakeDecision("armed", text, reason="wake_word_only")

        # 상용 음성 UI에서 흔히 쓰는 방식처럼 문장 시작 부분만 퍼지 매칭한다.
        # 문장 중간의 비슷한 발음은 호출로 인정하지 않아 오작동을 줄인다.
        try:
            from rapidfuzz import fuzz

            best_score = 0.0
            best_length = 0
            for alias in aliases:
                min_length = max(1, len(alias) - 1)
                max_length = min(len(normalized), len(alias) + 1)
                for length in range(min_length, max_length + 1):
                    score = float(fuzz.ratio(normalized[:length], alias))
                    if score > best_score:
                        best_score = score
                        best_length = length
            if best_score >= settings.wake_word_fuzzy_threshold:
                command = normalized[best_length:]
                with self._lock:
                    if command:
                        self._armed_until.pop(device_id, None)
                    else:
                        self._armed_until[device_id] = monotonic() + settings.wake_followup_seconds
                if command:
                    return WakeDecision("command", text, command, "wake_word_fuzzy_with_command")
                return WakeDecision("armed", text, reason="wake_word_fuzzy_only")
        except ImportError:
            pass

        now = monotonic()
        with self._lock:
            deadline = self._armed_until.get(device_id, 0.0)
            if deadline > now:
                self._armed_until.pop(device_id, None)
                return WakeDecision("command", text, text, "armed_followup")
            self._armed_until.pop(device_id, None)
        return WakeDecision("ignored", text, reason="wake_word_missing")


wake_word_gate = WakeWordGate()
