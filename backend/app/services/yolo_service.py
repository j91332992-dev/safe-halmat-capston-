import logging
from pathlib import Path
from typing import Any

from ..config import BASE_DIR, settings
from .camera_service import CAPTURE_DIR

logger = logging.getLogger(__name__)
_model: Any = None
_model_attempted = False


def analyze_frame_dummy(filename: str) -> dict:
    return {
        "mode": "dummy",
        "model": "not-loaded",
        "detections": [],
        "ppe": {},
        "hazards": {},
        "source": filename,
        "message": "YOLO 선택 패키지 또는 모델을 불러오지 못해 원본 프레임만 저장했습니다.",
    }


def get_yolo_model():
    global _model, _model_attempted
    if _model_attempted:
        return _model
    _model_attempted = True
    if not settings.yolo_enabled:
        return None
    candidates = [
        Path(settings.yolo_model_path),
        BASE_DIR / "best.pt",
        BASE_DIR / "yolov8_ppe.pt",
        BASE_DIR / "yolov8n.pt",
    ]
    model_path = next((path for path in candidates if path.exists()), None)
    if not model_path:
        logger.warning("YOLO 모델 파일을 찾지 못했습니다.")
        return None
    try:
        from ultralytics import YOLO

        _model = YOLO(str(model_path))
        logger.info("YOLO 모델 로드: %s", model_path)
    except Exception as exc:
        logger.warning("YOLO 로드 실패, 카메라 저장 모드로 동작: %s", exc)
        _model = None
    return _model


def _category(name: str) -> tuple[str | None, bool]:
    value = name.lower().replace("_", " ").replace("-", " ")
    negative = any(token in value.split() for token in ("no", "without", "missing", "not"))
    if "fire" in value or "flame" in value:
        return "fire", not negative
    if "smoke" in value:
        return "smoke", not negative
    if "helmet" in value or "hardhat" in value or "headgear" in value:
        return "helmet", not negative
    if "vest" in value:
        return "vest", not negative
    if "glove" in value:
        return "glove", not negative
    if "person" in value or "worker" in value:
        return "person", True
    return None, True


def analyze_frame(filename: str) -> dict:
    filepath = CAPTURE_DIR / filename
    if not filepath.exists():
        return analyze_frame_dummy(filename)
    model = get_yolo_model()
    if model is None:
        return analyze_frame_dummy(filename)
    try:
        import cv2

        results = model(str(filepath), verbose=False, conf=settings.yolo_confidence)
        result = results[0]
        names = result.names
        image = cv2.imread(str(filepath))
        detections: list[dict] = []
        ppe: dict[str, bool] = {}
        hazards = {"fire": False, "smoke": False}
        person_seen = False
        colors = {
            "helmet": (0, 70, 255),
            "glove": (0, 220, 255),
            "vest": (255, 120, 0),
            "fire": (0, 0, 255),
            "smoke": (140, 140, 140),
            "person": (40, 220, 80),
        }
        if result.boxes is not None:
            for box in result.boxes:
                class_id = int(box.cls[0].item())
                class_name = str(names.get(class_id, f"class_{class_id}"))
                category, positive = _category(class_name)
                if category is None:
                    continue
                confidence = round(float(box.conf[0].item()), 3)
                xyxy = [float(value) for value in box.xyxy[0].tolist()]
                detections.append({
                    "class": class_name,
                    "category": category,
                    "positive": positive,
                    "confidence": confidence,
                    "box": {"x1": xyxy[0], "y1": xyxy[1], "x2": xyxy[2], "y2": xyxy[3]},
                })
                if category == "person":
                    person_seen = True
                elif category in ("fire", "smoke"):
                    hazards[category] = hazards[category] or positive
                else:
                    if category not in ppe or not positive:
                        ppe[category] = positive
                if image is not None:
                    color = colors[category] if positive else (30, 30, 230)
                    start = (int(xyxy[0]), int(xyxy[1]))
                    end = (int(xyxy[2]), int(xyxy[3]))
                    cv2.rectangle(image, start, end, color, 2)
                    cv2.putText(image, f"{class_name} {confidence:.2f}", (start[0], max(18, start[1] - 7)), cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 2)
        if person_seen:
            for item in ("helmet", "vest", "glove"):
                ppe.setdefault(item, False)
        annotated_name = f"{filepath.stem}_annotated.jpg"
        if image is not None:
            x = 15
            for letter, key in (("H", "helmet"), ("V", "vest"), ("G", "glove"), ("F", "fire")):
                if (key in ppe and ppe[key]) or (key in hazards and hazards[key]):
                    cv2.putText(image, letter, (x, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.1, colors[key], 3)
                    x += 38
            cv2.imwrite(str(CAPTURE_DIR / annotated_name), image)
        return {
            "mode": "real",
            "model": Path(settings.yolo_model_path).name,
            "detections": detections,
            "ppe": ppe,
            "hazards": hazards,
            "person_seen": person_seen,
            "source": filename,
            "annotated_source": annotated_name,
        }
    except Exception as exc:
        logger.exception("YOLO 프레임 분석 실패: %s", exc)
        return analyze_frame_dummy(filename)