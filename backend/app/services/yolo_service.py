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
_ppe_crop_last_at: dict[str, float] = {}


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


def _ppe_threshold(category: str) -> float:
    if category == "glove":
        return float(settings.yolo_glove_confidence)
    if category == "vest":
        return float(settings.yolo_vest_confidence)
    return float(settings.yolo_ppe_confidence)


def _update_fire_confirmation(state: dict, max_confidence: float) -> tuple[bool, int]:
    required = max(1, int(settings.yolo_fire_confirm_frames))
    if max_confidence >= float(settings.yolo_fire_confidence):
        frames = int(state.get("fire_confirm_frames") or 0) + 1
    else:
        frames = 0
    state["fire_confirm_frames"] = frames
    return frames >= required, frames


def _update_confirmation(state: dict, key: str, max_confidence: float, threshold: float, required: int) -> tuple[bool, int]:
    """Confirm a hazard only when it is seen in consecutive frames."""
    count_key = f"{key}_confirm_frames"
    frames = int(state.get(count_key) or 0) + 1 if max_confidence >= threshold else 0
    state[count_key] = frames
    return frames >= max(1, required), frames


def _recent_count(state: dict, key: str, now: float, window_seconds: float, seen: bool) -> int:
    """Keep timestamped detections so PPE is never decided from one frame."""
    history_key = f"{key}_history"
    history = [float(value) for value in state.get(history_key, []) if now - float(value) <= window_seconds]
    if seen:
        history.append(now)
    state[history_key] = history
    return len(history)


def _update_observed_person_ppe(
    state: dict,
    *,
    person_seen: bool,
    ppe_seen: dict[str, bool],
    missing_required: int,
) -> tuple[dict[str, bool | None], dict[str, int]]:
    """Classify PPE only after consecutive person frames confirm absence."""
    required = max(1, int(missing_required))
    result: dict[str, bool | None] = {}
    counts: dict[str, int] = {}
    for item in ("helmet", "vest", "glove"):
        key = f"ppe_{item}_missing_consecutive"
        if not person_seen:
            count = 0
            result[item] = None
        elif bool(ppe_seen.get(item)):
            count = 0
            result[item] = True
        else:
            count = int(state.get(key) or 0) + 1
            result[item] = False if count >= required else None
        state[key] = count
        counts[item] = count
    return result, counts


def analyze_frame(filename: str, detail_enabled: bool = True) -> dict:
    filepath = CAPTURE_DIR / filename
    if not filepath.exists():
        return analyze_frame_dummy(filename)
    model = get_yolo_model()
    if model is None:
        return analyze_frame_dummy(filename)
    try:
        import cv2

        # Keep the inference parameters identical to test_webcam.py. Rendering
        # remains filtered to the safety categories used by the ESP dashboard.
        results = model(
            str(filepath),
            verbose=False,
            imgsz=settings.yolo_image_size,
            conf=settings.yolo_confidence,
        )
        result = results[0]
        names = result.names
        image = cv2.imread(str(filepath))
        detections: list[dict] = []
        ppe: dict[str, bool] = {}
        hazards = {"fire": False, "smoke": False}
        person_seen = False
        person_boxes: list[tuple[float, list[float]]] = []
        person_candidates: list[tuple[float, list[float]]] = []
        ppe_seen = {"helmet": False, "vest": False, "glove": False}
        max_fire_area_ratio = 0.0
        max_fire_confidence = 0.0
        max_smoke_confidence = 0.0
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
                if category in {"helmet", "vest", "glove"} and confidence < _ppe_threshold(category):
                    continue
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
                    # Model-level candidates (>= general 0.25 confidence) may guide
                    # the detail crop, but the final person/PPE decision still uses
                    # the unchanged 0.35 person threshold.
                    person_candidates.append((confidence, xyxy))
                    if confidence >= float(settings.yolo_person_confidence):
                        person_seen = True
                        person_boxes.append((confidence, xyxy))
                        horizontal_person = horizontal_person or aspect_ratio >= 1.5
                elif category == "fallen":
                    hazards["fallen"] = hazards.get("fallen", False) or positive
                    horizontal_person = horizontal_person or positive
                elif category in ("fire", "smoke"):
                    if category == "fire" and positive:
                        max_fire_confidence = max(max_fire_confidence, confidence)
                        max_fire_area_ratio = max(max_fire_area_ratio, area_ratio)
                    elif category == "smoke" and positive:
                        max_smoke_confidence = max(max_smoke_confidence, confidence)
                else:
                    if category in ppe_seen and positive:
                        # PPE는 신뢰도 높은 사람이 함께 보인 프레임만 누적한다.
                        ppe_seen[category] = True
                if image is not None:
                    color = colors[category] if positive else (30, 30, 230)
                    start = (int(xyxy[0]), int(xyxy[1]))
                    end = (int(xyxy[2]), int(xyxy[3]))
                    cv2.rectangle(image, start, end, color, 2)
                    cv2.putText(image, f"{class_name} {confidence:.2f}", (start[0], max(18, start[1] - 7)), cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 2)

        # Collapse highly-overlapping person boxes emitted for the same worker.
        # This changes display/tracking identity only, never confidence thresholds.
        person_detections = sorted(
            (item for item in detections if item.get("category") == "person"),
            key=lambda item: float(item.get("confidence") or 0.0),
            reverse=True,
        )
        unique_people: list[dict] = []
        for candidate in person_detections:
            box = candidate["box"]
            candidate_area = max(1.0, (box["x2"] - box["x1"]) * (box["y2"] - box["y1"]))
            duplicate = False
            for kept in unique_people:
                other = kept["box"]
                intersection = max(0.0, min(box["x2"], other["x2"]) - max(box["x1"], other["x1"])) * max(
                    0.0, min(box["y2"], other["y2"]) - max(box["y1"], other["y1"])
                )
                other_area = max(1.0, (other["x2"] - other["x1"]) * (other["y2"] - other["y1"]))
                containment = intersection / min(candidate_area, other_area)
                iou = intersection / max(1.0, candidate_area + other_area - intersection)
                vertical_overlap = max(0.0, min(box["y2"], other["y2"]) - max(box["y1"], other["y1"]))
                vertical_ratio = vertical_overlap / max(
                    1.0, min(box["y2"] - box["y1"], other["y2"] - other["y1"])
                )
                center_distance = abs(
                    ((box["x1"] + box["x2"]) * 0.5) - ((other["x1"] + other["x2"]) * 0.5)
                )
                max_width = max(box["x2"] - box["x1"], other["x2"] - other["x1"], 1.0)
                same_body_fragment = vertical_ratio >= 0.65 and center_distance <= max_width * 0.60
                if containment >= 0.70 or iou >= 0.50 or same_body_fragment:
                    duplicate = True
                    break
            if not duplicate:
                unique_people.append(candidate)
        detections = [item for item in detections if item.get("category") != "person"] + unique_people
        person_candidates = [
            (float(item["confidence"]), [item["box"][key] for key in ("x1", "y1", "x2", "y2")])
            for item in unique_people
        ]
        person_boxes = [
            item for item in person_candidates if item[0] >= float(settings.yolo_person_confidence)
        ]
        person_seen = bool(person_boxes)
        horizontal_person = any(
            (box[1][2] - box[1][0]) / max(1.0, box[1][3] - box[1][1]) >= 1.5
            for box in person_boxes
        )
        # The ESP frame stays on the fast 320px path.  PPE is much smaller than
        # a person, so track the best person candidate and inspect only that ROI
        # at the model's native 640 training size.  Thresholds remain unchanged.
        ppe_crop_used = False
        ppe_crop_attempted = False
        state_key = filepath.name.split("_", 1)[0]
        state = _vision_state.setdefault(state_key, {})
        crop_now = time.monotonic()
        if person_candidates:
            _, current_candidate = max(person_candidates, key=lambda item: item[0])
            state["person_track_box"] = current_candidate
            state["person_track_at"] = crop_now
        tracked_box = state.get("person_track_box")
        tracked_at = float(state.get("person_track_at") or 0.0)
        if crop_now - tracked_at > float(settings.yolo_person_track_seconds):
            tracked_box = None
            state.pop("person_track_box", None)
            state.pop("person_track_at", None)
        crop_due = (
            crop_now - _ppe_crop_last_at.get(state_key, 0.0)
            >= float(settings.yolo_ppe_detail_interval_seconds)
        )
        if detail_enabled and image is not None and tracked_box and crop_due:
            _ppe_crop_last_at[state_key] = crop_now
            ppe_crop_attempted = True
            crop_source = cv2.imread(str(filepath))
            if crop_source is not None:
                person_xyxy = [float(value) for value in tracked_box]
                height, width = crop_source.shape[:2]
                person_width = max(1.0, person_xyxy[2] - person_xyxy[0])
                person_height = max(1.0, person_xyxy[3] - person_xyxy[1])
                # Keep hands near the sides and PPE near the head/waist in-frame.
                pad_x = person_width * 0.20
                pad_y = person_height * 0.14
                crop_x1 = max(0, int(person_xyxy[0] - pad_x))
                crop_y1 = max(0, int(person_xyxy[1] - pad_y))
                crop_x2 = min(width, int(person_xyxy[2] + pad_x))
                crop_y2 = min(height, int(person_xyxy[3] + pad_y))
                crop = crop_source[crop_y1:crop_y2, crop_x1:crop_x2]
                if crop.size:
                    # Mild unsharp masking restores JPEG-softened glove/vest edges.
                    blurred = cv2.GaussianBlur(crop, (0, 0), 1.0)
                    detail_crop = cv2.addWeighted(crop, 1.35, blurred, -0.35, 0)
                    detail_passes = (
                        (detail_crop, int(settings.yolo_ppe_detail_image_size), "sharp640"),
                        (crop, 960, "original960"),
                    )
                    best_detail: dict[str, dict] = {}
                    for detail_image, detail_size, detail_source in detail_passes:
                        crop_result = model(
                            detail_image,
                            verbose=False,
                            imgsz=detail_size,
                            conf=float(settings.yolo_confidence),
                        )[0]
                        crop_names = crop_result.names
                        if crop_result.boxes is None:
                            continue
                        for box in crop_result.boxes:
                            class_id = int(box.cls[0].item())
                            class_name = str(crop_names.get(class_id, f"class_{class_id}"))
                            category, positive = _category(class_name)
                            confidence = round(float(box.conf[0].item()), 3)
                            local_xyxy = [float(value) for value in box.xyxy[0].tolist()]
                            color_evidence = None
                            # The current model localizes the red work glove as
                            # `hand`. Require both model-level hand confidence and
                            # dominant red textile pixels; bare hands fail this.
                            if class_name.strip().lower() == "hand":
                                hx1 = max(0, int(local_xyxy[0]))
                                hy1 = max(0, int(local_xyxy[1]))
                                hx2 = min(detail_image.shape[1], int(local_xyxy[2]))
                                hy2 = min(detail_image.shape[0], int(local_xyxy[3]))
                                hand_roi = detail_image[hy1:hy2, hx1:hx2]
                                red_ratio = 0.0
                                if hand_roi.size:
                                    hsv = cv2.cvtColor(hand_roi, cv2.COLOR_BGR2HSV)
                                    hue, saturation, value = cv2.split(hsv)
                                    red_mask = ((hue < 12) | (hue > 168)) & (saturation > 75) & (value > 45)
                                    red_ratio = float(red_mask.mean())
                                if confidence >= float(settings.yolo_glove_confidence) and red_ratio >= 0.35:
                                    class_name = "red_work_glove"
                                    category, positive = "glove", True
                                    color_evidence = round(red_ratio, 3)
                                else:
                                    continue
                            if category not in {"helmet", "vest", "glove"} or not positive:
                                continue
                            if confidence < _ppe_threshold(category):
                                continue
                            previous = best_detail.get(category)
                            if previous is not None and float(previous["confidence"]) >= confidence:
                                continue
                            best_detail[category] = {
                                "class_name": class_name,
                                "confidence": confidence,
                                "local_xyxy": local_xyxy,
                                "color_evidence": color_evidence,
                                "detail_source": detail_source,
                            }
                    for category, best in best_detail.items():
                        local_xyxy = best["local_xyxy"]
                        confidence = float(best["confidence"])
                        xyxy = [
                            local_xyxy[0] + crop_x1,
                            local_xyxy[1] + crop_y1,
                            local_xyxy[2] + crop_x1,
                            local_xyxy[3] + crop_y1,
                        ]
                        ppe_seen[category] = True
                        ppe_crop_used = True
                        box_width = max(0.0, xyxy[2] - xyxy[0])
                        box_height = max(0.0, xyxy[3] - xyxy[1])
                        frame_area = float(height * width)
                        detections.append({
                            "class": best["class_name"],
                            "category": category,
                            "positive": True,
                            "confidence": confidence,
                            "area_ratio": round((box_width * box_height) / frame_area, 4),
                            "aspect_ratio": round(box_width / max(box_height, 1.0), 3),
                            "box": {"x1": xyxy[0], "y1": xyxy[1], "x2": xyxy[2], "y2": xyxy[3]},
                            "source": f"tracked_person_{best['detail_source']}",
                            **({"red_pixel_ratio": best["color_evidence"]} if best["color_evidence"] is not None else {}),
                        })
                        color = colors[category]
                        start = (int(xyxy[0]), int(xyxy[1]))
                        end = (int(xyxy[2]), int(xyxy[3]))
                        cv2.rectangle(image, start, end, color, 2)
                        cv2.putText(image, f"{category} {confidence:.2f} detail", (start[0], max(18, start[1] - 7)), cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 2)
        now = time.monotonic()
        previous_area = float(state.get("fire_area_ratio") or 0.0)
        previous_at = float(state.get("fire_at") or now)
        elapsed = max(0.001, now - previous_at)
        expansion_rate = (max_fire_area_ratio - previous_area) / previous_area if previous_area > 0 and elapsed <= 1.5 else 0.0
        state["fire_area_ratio"] = max_fire_area_ratio
        state["fire_at"] = now
        window = float(settings.yolo_ppe_window_seconds)
        person_frames = _recent_count(state, "person", now, window, person_seen)
        ppe_frames = {
            item: _recent_count(state, f"ppe_{item}", now, window, person_seen and ppe_seen[item])
            for item in ppe_seen
        }
        ppe, missing_consecutive_frames = _update_observed_person_ppe(
            state, person_seen=person_seen, ppe_seen=ppe_seen,
            missing_required=int(settings.yolo_ppe_missing_consecutive_frames),
        )
        ppe_active = person_seen
        if horizontal_person:
            state.setdefault("fallen_since", now)
        else:
            state.pop("fallen_since", None)
        fallen_confirmed = bool(hazards.get("fallen")) or (
            horizontal_person and now - float(state.get("fallen_since", now)) >= 3.0
        )
        fire_confirmed, fire_confirm_frames = _update_fire_confirmation(state, max_fire_confidence)
        smoke_confirmed, smoke_confirm_frames = _update_confirmation(
            state,
            "smoke",
            max_smoke_confidence,
            float(settings.yolo_smoke_confidence),
            int(settings.yolo_smoke_confirm_frames),
        )
        hazards.update({
            "fire": fire_confirmed,
            "fire_candidate_confidence": round(max_fire_confidence, 3),
            "fire_confirm_frames": fire_confirm_frames,
            "smoke_candidate_confidence": round(max_smoke_confidence, 3),
            "smoke_confirm_frames": smoke_confirm_frames,
            "fire_area_ratio": round(max_fire_area_ratio, 4),
            "fire_expansion_rate": round(max(0.0, expansion_rate), 4),
            "large_fire": bool(fire_confirmed and (max_fire_area_ratio >= 0.15 or expansion_rate >= 0.20)),
            "small_fire": bool(fire_confirmed and max_fire_area_ratio < 0.05),
            "smoke": smoke_confirmed,
            "fallen": fallen_confirmed,
        })
        if person_seen:
            for item in ("helmet", "vest", "glove"):
                ppe.setdefault(item, False)
        annotated_jpeg: bytes | None = None
        if image is not None:
            x = 15
            for letter, key in (("H", "helmet"), ("V", "vest"), ("G", "glove"), ("F", "fire")):
                if (key in ppe and ppe[key]) or (key in hazards and hazards[key]):
                    cv2.putText(image, letter, (x, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.1, colors[key], 3)
                    x += 38
            encoded, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88])
            if encoded:
                annotated_jpeg = jpeg.tobytes()
        return {
            "mode": "real",
            "model": Path(settings.yolo_model_path).name,
            "detections": detections,
            "ppe": ppe,
            "ppe_judgement": {
                "active": ppe_active,
                "status": "active" if ppe_active else "pending_person",
                "person_frames": person_frames,
                "person_frames_required": int(settings.yolo_ppe_person_frames),
                "ppe_frames": ppe_frames,
                "ppe_frames_required": int(settings.yolo_ppe_worn_frames),
                "missing_consecutive_frames": missing_consecutive_frames,
                "missing_frames_required": int(settings.yolo_ppe_missing_consecutive_frames),
                "subject_scope": "observed_person",
                "window_seconds": window,
            },
            "hazards": hazards,
            "person_seen": person_seen,
            "ppe_crop_used": ppe_crop_used,
            "ppe_crop_attempted": ppe_crop_attempted,
            "source": filename,
            # The normal fast path keeps the latest annotated frame in memory.
            # The router writes evidence to disk only when a safety state
            # actually needs a durable event record.
            "annotated_source": None,
            "_annotated_jpeg": annotated_jpeg,
        }
    except Exception as exc:
        logger.exception("YOLO 프레임 분석 실패: %s", exc)
        return analyze_frame_dummy(filename)
