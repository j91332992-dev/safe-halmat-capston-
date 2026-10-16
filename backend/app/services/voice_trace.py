"""Local bounded diagnostic records. Never record credentials or raw API errors."""
import logging
from datetime import datetime, timezone
from pathlib import Path

from ..config import BASE_DIR, settings
from .uwb_log_service import BoundedJsonlLog

_log = None


def record_voice(stage: str, trace_id: str, **fields):
    global _log
    if not settings.voice_trace_enabled:
        return
    try:
        if _log is None:
            _log = BoundedJsonlLog(BASE_DIR / "logs" / "voice-pipeline.jsonl",
                settings.voice_trace_max_bytes, settings.voice_trace_backups,
                settings.voice_trace_retention_days)
        _log.append({"stage": stage, "trace_id": Path(trace_id).name,
                     "at": datetime.now(timezone.utc).isoformat(), **fields})
    except (OSError, ValueError):
        logging.getLogger("uvicorn.error").warning("Voice trace write failed")
