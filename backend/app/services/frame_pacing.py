"""Deadline pacing with at most one interval of catch-up, never a stale queue."""
def next_deadline(previous: float, started: float, interval: float) -> float:
    return max(previous + interval, started)

def inference_interval(normal_interval, voice_active, gpu_active, gpu_voice_fps):
    # Voice no longer imposes a separate camera FPS cap.
    return normal_interval
