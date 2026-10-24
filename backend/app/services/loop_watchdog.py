"""Bounded stack evidence for a stalled event loop; no locals or source text."""
import sys
import threading
import time
import traceback

from .camera_trace import record_analysis


class LoopWatchdog:
    def __init__(self):
        self._stop = threading.Event()
        self._thread = None
        self._owner = None
        self._pulse = 0.0

    def start(self):
        if self._thread and self._thread.is_alive() and not self._stop.is_set():
            return
        self._owner = threading.get_ident()
        self._pulse = time.monotonic()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._watch, args=(self._stop,), name="loop-stall-observer", daemon=True)
        self._thread.start()

    def pulse(self):
        self._pulse = time.monotonic()

    def stop(self):
        self._stop.set()

    def _watch(self, stop):
        last_record = 0.0
        while not stop.wait(.025):
            now = time.monotonic()
            age = now - self._pulse
            if age < .15 or now - last_record < 1.0:
                continue
            frame = sys._current_frames().get(self._owner)
            if frame is None:
                continue
            stack = [{"file": item.filename, "line": item.lineno, "function": item.name}
                     for item in traceback.extract_stack(frame, limit=32)]
            del frame
            record_analysis(lane="loop_stall", heartbeat_age_ms=round(age * 1000, 2), stack=stack)
            last_record = now


loop_watchdog = LoopWatchdog()
