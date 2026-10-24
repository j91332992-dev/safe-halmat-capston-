"""Bounded JSONL observations, independent of position-history change detection."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock
import time


class BoundedJsonlLog:
    """One writer per path/process; total files <= backups + 1, age in days.

    Rotation and expiry are checked on every append (and startup). Do not share
    a path across server processes; use one Uvicorn worker for capture sessions.
    """

    def __init__(self, path: Path, max_bytes: int = 10 * 1024 * 1024,
                 backups: int = 4, retention_days: float = 7, expiry_check_seconds: float = 0):
        if max_bytes < 1024 or not 0 <= backups <= 100 or retention_days <= 0:
            raise ValueError("Invalid UWB log limits")
        self.path = Path(path)
        self.max_bytes, self.backups = max_bytes, backups
        self.retention_seconds = retention_days * 86400
        self.expiry_check_seconds = max(0, expiry_check_seconds)
        self.last_expiry_check = time.monotonic()
        self.rotation_retry_after = 0.0
        self.rotation_blocked = 0
        self.lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._expire()

    def _file(self, index: int) -> Path:
        return self.path if index == 0 else Path(f"{self.path}.{index}")

    def _expire(self):
        cutoff = time.time() - self.retention_seconds
        for index in range(self.backups + 1):
            path = self._file(index)
            if path.exists():
                # Use the first record's age, not mtime which every append resets.
                with path.open("rb") as stream:
                    first_line = stream.readline(self.max_bytes + 1)
                try:
                    oldest = json.loads(first_line).get("logged_at_unix", path.stat().st_mtime)
                except (ValueError, TypeError):
                    oldest = path.stat().st_mtime
                if oldest < cutoff:
                    path.unlink()

    def append(self, record: dict) -> None:
        record = {**record, "logged_at_unix": time.time()}
        data = (json.dumps(record, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
        if len(data) > self.max_bytes:
            raise ValueError("UWB observation exceeds log file limit")
        with self.lock:
            if time.monotonic() - self.last_expiry_check >= self.expiry_check_seconds:
                self._expire()
                self.last_expiry_check = time.monotonic()
            size = self.path.stat().st_size if self.path.exists() else 0
            if size + len(data) > self.max_bytes and time.monotonic() >= self.rotation_retry_after:
                try:
                    self._file(self.backups).unlink(missing_ok=True)
                    for index in range(self.backups - 1, -1, -1):
                        source = self._file(index)
                        if source.exists():
                            source.replace(self._file(index + 1))
                    size = 0
                except PermissionError:
                    # A Windows reader can briefly deny rename. Preserve the
                    # current file and defer rotation rather than blocking UWB.
                    self.rotation_blocked += 1
                    self.rotation_retry_after = time.monotonic() + 1
            if size + len(data) > 2 * self.max_bytes:
                raise OSError('JSONL rotation blocked; bounded overflow exhausted')
            with self.path.open("ab") as stream:
                stream.write(data)


_log = None
_init_lock = Lock()
_last_error_log = 0.0
_write_errors = 0


def record_observation(record: dict) -> bool:
    from ..config import settings
    global _log, _last_error_log, _write_errors
    try:
        with _init_lock:
            if _log is None:
                _log = BoundedJsonlLog(Path(settings.uwb_log_path), settings.uwb_log_max_bytes,
                                       settings.uwb_log_backups, settings.uwb_log_retention_days,
                                       expiry_check_seconds=60)
        _log.append(record)
        return True
    except (OSError, ValueError):
        _write_errors += 1
        if time.monotonic() - _last_error_log >= 5:
            _last_error_log = time.monotonic()
            logging.getLogger(__name__).exception("UWB observation log write failed")
        return False


def observation_log_stats():
    return {'write_errors': _write_errors, 'rotation_blocked': _log.rotation_blocked if _log else 0}
