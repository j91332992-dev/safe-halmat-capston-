"""Bounded per-analysis detection evidence; confidence is not measured accuracy."""
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timezone

_logger = None

def record_analysis(**fields):
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
        _logger.info(json.dumps({'at': datetime.now(timezone.utc).isoformat(), **fields}, ensure_ascii=False))
    except Exception:
        logging.getLogger(__name__).exception('Camera trace write failed')
