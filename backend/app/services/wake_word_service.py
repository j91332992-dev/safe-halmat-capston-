from dataclasses import dataclass
from threading import Lock
from time import monotonic

from ..config import settings
from .speech_service import normalize, resolve_intent


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

    def evaluate(self, device_id: str, transcript: str) -> WakeDecision:
        text = (transcript or "").strip()
        normalized = normalize(text)
        if not normalized:
            return WakeDecision("ignored", text, reason="stt_empty")

        # 생명안전 명령은 웨이크워드 없이도 즉시 처리한다.
        intent, confidence = resolve_intent(text)
        if intent in {"emergency", "help", "fire_report"} and confidence >= 0.95:
            with self._lock:
                self._armed_until.pop(device_id, None)
            return WakeDecision("command", text, text, "life_critical_bypass")

        aliases = sorted(
            {normalize(item) for item in settings.wake_word_alias_list if normalize(item)},
            key=len,
            reverse=True,
        )
        for alias in aliases:
            index = normalized.find(alias)
            if index < 0:
                continue
            command = normalized[:index] + normalized[index + len(alias):]
            with self._lock:
                if command:
                    self._armed_until.pop(device_id, None)
                else:
                    self._armed_until[device_id] = monotonic() + settings.wake_followup_seconds
            if command:
                return WakeDecision("command", text, command, "wake_word_with_command")
            return WakeDecision("armed", text, reason="wake_word_only")

        now = monotonic()
        with self._lock:
            deadline = self._armed_until.get(device_id, 0.0)
            if deadline > now:
                self._armed_until.pop(device_id, None)
                return WakeDecision("command", text, text, "armed_followup")
            self._armed_until.pop(device_id, None)
        return WakeDecision("ignored", text, reason="wake_word_missing")


wake_word_gate = WakeWordGate()
