from dataclasses import dataclass
from threading import Lock
from time import monotonic

from ..config import settings
from .speech_service import normalize, resolve_intent


@dataclass(frozen=True)
class ExecutedCommand:
    intent: str
    text: str
    executed_at: float


class VoiceExecutionGate:
    """Allow one ordinary action per short wake-command capture window."""

    _SAFETY_INTENTS = {"emergency", "help", "fire_report"}
    _CONTROL_INTENTS = {"stop_speaking", "hang_up"}

    def __init__(self) -> None:
        self._recent: dict[str, ExecutedCommand] = {}
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._recent.clear()

    def allow(self, device_id: str, text: str) -> tuple[bool, str]:
        intent, _ = resolve_intent(text)
        if intent == "unknown":
            return True, "unknown_not_limited"
        normalized = normalize(text)
        now = monotonic()
        with self._lock:
            previous = self._recent.get(device_id)
            if previous and now - previous.executed_at < settings.voice_command_cooldown_seconds:
                same_command = previous.intent == intent or previous.text == normalized
                if same_command:
                    return False, "duplicate_command"
                if intent not in self._SAFETY_INTENTS and intent not in self._CONTROL_INTENTS:
                    return False, "overlapping_command"
            self._recent[device_id] = ExecutedCommand(intent, normalized, now)
        return True, "accepted"


voice_execution_gate = VoiceExecutionGate()
