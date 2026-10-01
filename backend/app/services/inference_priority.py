import asyncio
from threading import Event, Lock


_voice_idle = Event()
_voice_idle.set()
_state_lock = Lock()
_active_voice_requests = 0


async def voice_priority():
    """Mark an audio/assistant request as higher priority than vision inference."""
    global _active_voice_requests
    with _state_lock:
        _active_voice_requests += 1
        _voice_idle.clear()
    try:
        yield
    finally:
        with _state_lock:
            _active_voice_requests = max(0, _active_voice_requests - 1)
            if _active_voice_requests == 0:
                _voice_idle.set()


async def wait_for_voice_idle() -> None:
    """Do not start a new YOLO inference while voice work is active."""
    while not _voice_idle.is_set():
        await asyncio.sleep(0.02)


def voice_requests_active() -> int:
    with _state_lock:
        return _active_voice_requests
