def analyze_frame_dummy(filename: str) -> dict:
    """실제 모델 파일이 준비되기 전에도 동일 스키마를 반환한다."""
    return {
        "mode": "dummy",
        "model": "YOLOv8n-not-loaded",
        "detections": [],
        "ppe": {"vest": True, "glove": True},
        "hazards": {"fire": False, "smoke": False},
        "source": filename,
    }

