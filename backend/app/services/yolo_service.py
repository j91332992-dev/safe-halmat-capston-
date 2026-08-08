import logging
import time
from pathlib import Path
from typing import Any

from ..config import BASE_DIR, settings
from .camera_service import CAPTURE_DIR

logger = logging.getLogger(__name__)
_model: Any = None
_model_attempted = False
_vision_state: dict[str, dict] = {}


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
    if "fall" in value or "lying" in value or "man down" in value:
        return "fallen", True
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
        max_fire_area_ratio = 0.0
        horizontal_person = False
        colors = {
            "helmet": (0, 70, 255),
            "glove": (0, 220, 255),
            "vest": (255, 120, 0),
            "fire": (0, 0, 255),
            "smoke": (140, 140, 140),
            "person": (40, 220, 80),
            "fallen": (0, 0, 255),
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
                box_width = max(0.0, xyxy[2] - xyxy[0])
                box_height = max(0.0, xyxy[3] - xyxy[1])
                frame_area = float(image.shape[0] * image.shape[1]) if image is not None else 0.0
                area_ratio = (box_width * box_height / frame_area) if frame_area else 0.0
                aspect_ratio = box_width / max(box_height, 1.0)
                detections.append({
                    "class": class_name,
                    "category": category,
                    "positive": positive,
                    "confidence": confidence,
                    "area_ratio": round(area_ratio, 4),
                    "aspect_ratio": round(aspect_ratio, 3),
                    "box": {"x1": xyxy[0], "y1": xyxy[1], "x2": xyxy[2], "y2": xyxy[3]},
                })
                if category == "person":
                    person_seen = True
                    horizontal_person = horizontal_person or aspect_ratio >= 1.5
                elif category == "fallen":
                    hazards["fallen"] = hazards.get("fallen", False) or positive
                    horizontal_person = horizontal_person or positive
                elif category in ("fire", "smoke"):
                    hazards[category] = hazards[category] or positive
                    if category == "fire" and positive:
                        max_fire_area_ratio = max(max_fire_area_ratio, area_ratio)
                else:
                    if category not in ppe or not positive:
                        ppe[category] = positive
                if image is not None:
                    color = colors[category] if positive else (30, 30, 230)
                    start = (int(xyxy[0]), int(xyxy[1]))
                    end = (int(xyxy[2]), int(xyxy[3]))
                    cv2.rectangle(image, start, end, color, 2)
                    cv2.putText(image, f"{class_name} {confidence:.2f}", (start[0], max(18, start[1] - 7)), cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 2)
        now = time.monotonic()
        state_key = filepath.name.split("_", 1)[0]
        state = _vision_state.setdefault(state_key, {})
        previous_area = float(state.get("fire_area_ratio") or 0.0)
        previous_at = float(state.get("fire_at") or now)
        elapsed = max(0.001, now - previous_at)
        expansion_rate = (max_fire_area_ratio - previous_area) / previous_area if previous_area > 0 and elapsed <= 1.5 else 0.0
        state["fire_area_ratio"] = max_fire_area_ratio
        state["fire_at"] = now
        if horizontal_person:
            state.setdefault("fallen_since", now)
        else:
            state.pop("fallen_since", None)
        fallen_confirmed = bool(hazards.get("fallen")) or (
            horizontal_person and now - float(state.get("fallen_since", now)) >= 3.0
        )
        hazards.update({
            "fire_area_ratio": round(max_fire_area_ratio, 4),
            "fire_expansion_rate": round(max(0.0, expansion_rate), 4),
            "large_fire": bool(max_fire_area_ratio >= 0.15 or expansion_rate >= 0.20),
            "small_fire": bool(hazards.get("fire") and max_fire_area_ratio < 0.05),
            "fallen": fallen_confirmed,
        })
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
