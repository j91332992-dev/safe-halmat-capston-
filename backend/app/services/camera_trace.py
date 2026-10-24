"""Bounded per-analysis detection evidence; confidence is not measured accuracy."""
import json
import atexit
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timezone
from queue import Queue, Full
from threading import Thread, Lock

_logger = None
_queue = Queue(maxsize=512)
_thread = None
_init_lock = Lock()
_stats = {'enqueued': 0, 'written': 0, 'dropped': 0, 'errors': 0}


def trace_stats():
    return {**_stats, 'queue_depth': _queue.qsize(), 'queue_capacity': _queue.maxsize}


def _writer():
    global _logger
    while True:
        fields = _queue.get()
        try:
            if fields is None:
                return
            _write(fields)
            _stats['written'] += 1
        except Exception:
            _stats['errors'] += 1
        finally:
            _queue.task_done()


def _shutdown():
    if _thread and _thread.is_alive():
        try:
            _queue.put_nowait(None)
        except Full:
            return
        _thread.join(timeout=3)


atexit.register(_shutdown)

def record_analysis(**fields):
    global _thread
    # No file I/O or JSON serialization on the audio/video event loop.
    with _init_lock:
        if _thread is None:
            _thread = Thread(target=_writer, name='camera-trace-writer', daemon=True)
            _thread.start()
    try:
        _queue.put_nowait({'at': datetime.now(timezone.utc).isoformat(), **fields})
        _stats['enqueued'] += 1
    except Full:
        _stats['dropped'] += 1


def _write(fields):
    global _logger
    try:
        if _logger is None:
            path = Path(__file__).resolve().parents[2] / 'logs' / 'camera-analysis.jsonl'
            path.parent.mkdir(parents=True, exist_ok=True)
            logger = logging.getLogger('hanmir.camera_trace')
            logger.setLevel(logging.INFO)
            logger.propagate = False
            if not logger.handlers:
                handler = RotatingFileHandler(path, maxBytes=20*1024*1024, backupCount=3, encoding='utf-8')
                handler.setFormatter(logging.Formatter('%(message)s'))
                logger.addHandler(handler)
            _logger = logger
        _logger.info(json.dumps(fields, ensure_ascii=False))
    except Exception:
        logging.getLogger(__name__).exception('Camera trace write failed')
