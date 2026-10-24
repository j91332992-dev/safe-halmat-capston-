"""Local bounded diagnostic records. Never record credentials or raw API errors."""
import atexit
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue, Full
from threading import Thread, Lock

from ..config import BASE_DIR, settings
from .uwb_log_service import BoundedJsonlLog

_log = None
_queue = Queue(maxsize=512)
_writer_thread = None
_init_lock = Lock()
_stats = dict(enqueued=0, written=0, dropped=0, errors=0)


def voice_trace_stats():
    return {**_stats, "queue_depth": _queue.qsize(), "queue_capacity": _queue.maxsize}


def _write_records():
    global _log
    while True:
        record = _queue.get()
        try:
            if record is None:
                return
            if _log is None:
                _log = BoundedJsonlLog(BASE_DIR / "logs" / "voice-pipeline.jsonl",
                    settings.voice_trace_max_bytes, settings.voice_trace_backups,
                    settings.voice_trace_retention_days)
            _log.append(record)
            _stats["written"] += 1
        except Exception:
            _stats["errors"] += 1
        finally:
            _queue.task_done()


def _drain():
    if _writer_thread and _writer_thread.is_alive():
        try:
            _queue.put_nowait(None)
        except Full:
            return
        _writer_thread.join(timeout=3)


atexit.register(_drain)


def record_voice(stage: str, trace_id: str, **fields):
    global _writer_thread
    if not settings.voice_trace_enabled:
        return
    # Preserve the caller's timestamp; disk latency never holds call relay/STT.
    with _init_lock:
        if _writer_thread is None:
            _writer_thread = Thread(target=_write_records, name="voice-trace-writer", daemon=True)
            _writer_thread.start()
    try:
        _queue.put_nowait({"stage": stage, "trace_id": Path(trace_id).name,
                          "at": datetime.now(timezone.utc).isoformat(), **fields})
        _stats["enqueued"] += 1
    except Full:
        _stats["dropped"] += 1
