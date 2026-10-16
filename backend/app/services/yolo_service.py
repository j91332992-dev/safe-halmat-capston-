import logging
import os
import time
from pathlib import Path
from typing import Any

from ..config import BASE_DIR, settings
from .camera_service import CAPTURE_DIR
from .camera_brightness import brighten, preview_image

logger = logging.getLogger(__name__)
_model: Any = None
_model_attempted = False
_fast_gpu_failed = False
_vision_state: dict[str, dict] = {}
_ppe_crop_last_at: dict[str, float] = {}


def _limit_predict_threads(_predictor):
    import torch
    threads=int(os.environ.get('HANMIR_YOLO_CPU_THREADS','3'))
    if torch.get_num_threads()!=threads:
        torch.set_num_threads(threads)


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
    if settings.yolo_fast_openvino_gpu and os.environ.get('HANMIR_YOLO_LANE')=='fast' and not _fast_gpu_failed:
        try:
            from .openvino_yolo import load_openvino_yolo
            _model=load_openvino_yolo(settings.yolo_openvino_model_path,3,'GPU')
            return _model
        except Exception:
            logger.exception('GPU initialization failed; using original PyTorch model')
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
        # YOLO can recreate its predictor on the first call or argument changes.
        # This callback runs after setup and before inference on EVERY call.
        _model.add_callback('on_predict_start',_limit_predict_threads)
        if settings.yolo_detail_hybrid_gpu and os.environ.get('HANMIR_YOLO_LANE')=='detail':
            try:
                from .openvino_yolo import load_openvino_yolo
                from .detail_model import HybridDetailModel
                gpu=load_openvino_yolo(settings.yolo_openvino_model_path,2,'GPU')
                gpu960 = load_openvino_yolo(settings.yolo_detail_gpu960_model_path,2,'GPU') if settings.yolo_detail_gpu960_model_path else None
                _model=HybridDetailModel(_model,gpu,gpu960)
            except Exception:
                logger.exception('Detail GPU initialization failed; preserving CPU model')
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
    worker_started=time.perf_counter()
    global _model, _model_attempted, _fast_gpu_failed
    filepath = CAPTURE_DIR / filename
    if not filepath.exists():
        return analyze_frame_dummy(filename)
    model = get_yolo_model()
    if model is None:
        return analyze_frame_dummy(filename)
    if hasattr(model,'timings'):model.timings.clear()
    try:
        import cv2

        # Keep the inference parameters identical to test_webcam.py. Rendering
        # remains filtered to the safety categories used by the ESP dashboard.
        decode_started=time.perf_counter()
        source_image=cv2.imread(str(filepath))
        if source_image is None:
            return analyze_frame_dummy(filename)
        corrected_image=brighten(source_image) if detail_enabled else None
        decode_ms=(time.perf_counter()-decode_started)*1000
        results = model(
            source_image,
            verbose=False,
            imgsz=settings.yolo_image_size,
            conf=settings.yolo_confidence,
        )
        result = results[0]
        names = result.names
        image = preview_image(source_image)
        detections: list[dict] = []
        model_candidates: list[dict] = []
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
            "helmet": (0, 220, 255),
            "glove": (220, 70, 180),
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
                model_candidates.append({"class":class_name,"confidence":round(float(box.conf[0].item()),3),
                    "box":box.xyxy[0].tolist(),"pass":"full"})
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
            os.environ.get("HANMIR_YOLO_LANE") == "detail" or
            crop_now - _ppe_crop_last_at.get(state_key, 0.0)
            >= float(settings.yolo_ppe_detail_interval_seconds)
        )
        if detail_enabled and image is not None and tracked_box and crop_due:
            _ppe_crop_last_at[state_key] = crop_now
            ppe_crop_attempted = True
            crop_source = corrected_image
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
                    detail_passes = [
                        (detail_crop, int(settings.yolo_ppe_detail_image_size), "sharp640"),
                    ]
                    if settings.yolo_ppe_detail_960_enabled:
                        detail_passes.append((crop, 960, "original960"))
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
                            model_candidates.append({"class":class_name,"confidence":round(float(box.conf[0].item()),3),
                                "box":box.xyxy[0].tolist(),"pass":detail_source,
                                "crop_origin":[crop_x1,crop_y1]})
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
        # Body localization is only a crop proposal, never proof of a vest.
        if settings.yolo_vest_body_probe and detail_enabled and len(person_boxes)==1 and not ppe_seen.get('vest'):
            px1,py1,px2,py2=person_boxes[0][1]
            bodies=[c for c in model_candidates if c['pass']=='full' and c['class'].lower()=='body' and c['confidence']>=.5
                and px1 <= (c['box'][0]+c['box'][2])/2 <= px2 and py1 <= (c['box'][1]+c['box'][3])/2 <= py2]
            if bodies:
                bx1,by1,bx2,by2=max(bodies,key=lambda c:c['confidence'])['box']
                bw,bh=bx2-bx1,by2-by1
                ox=max(0,int(bx1-bw*.1));oy=max(0,int(by1-bh*.1))
                roi=corrected_image[oy:min(corrected_image.shape[0],int(by2+bh*.1)),ox:min(corrected_image.shape[1],int(bx2+bw*.1))]
                if roi.size:
                    probe=model(roi,imgsz=640,conf=settings.yolo_confidence,verbose=False)[0]
                    best=None
                    for b in probe.boxes:
                        name=probe.names[int(b.cls[0])];conf=float(b.conf[0]);coords=b.xyxy[0].tolist()
                        model_candidates.append(dict(confidence=round(conf,3),box=coords,**{'class':name,'pass':'body640','crop_origin':[ox,oy]}))
                        category,positive=_category(name)
                        if category=='vest' and positive and conf>=_ppe_threshold('vest') and (best is None or conf>best['confidence']):
                            best=dict(category='vest',positive=True,confidence=round(conf,3),**{'class':name,'box':dict(x1=coords[0]+ox,y1=coords[1]+oy,x2=coords[2]+ox,y2=coords[3]+oy),'source':'body640'})
                    if best:
                        detections.append(best);ppe_seen['vest']=True
        # Run only in the independent detail lane. A head candidate locates a
        # region; it never proves helmet use. Preserve the helmet threshold.
        head_probe_attempted = False
        if settings.yolo_head_detail_enabled and detail_enabled and person_seen and not ppe_seen.get("helmet"):
            head_candidates = [c for c in model_candidates if c['pass']=='full' and c['class'].lower()=='head' and c['confidence']>=.5]
            if head_candidates and len(person_boxes)==1:
                px1,py1,px2,py2=person_boxes[0][1]
                head_candidates=[c for c in head_candidates if px1 <= (c['box'][0]+c['box'][2])/2 <= px2
                    and py1 <= (c['box'][1]+c['box'][3])/2 <= py1+(py2-py1)*.5]
                if head_candidates:
                    head=min(head_candidates,key=lambda c:c['box'][1])['box']
                    hx1,hy1,hx2,hy2=head; hw=hx2-hx1; hh=hy2-hy1
                    original=corrected_image
                    ox=max(0,int(hx1-hw*.3)); oy=max(0,int(hy1-hh*.3))
                    roi=original[oy:min(original.shape[0],int(hy2+hh*.4)),ox:min(original.shape[1],int(hx2+hw*.3))]
                    best_head=None
                    if roi.size:
                        head_probe_attempted=True
                        for probe_size in (640,960):
                            if settings.yolo_detail_early_exit and best_head is not None:
                                break
                            probe=model(roi,imgsz=probe_size,conf=settings.yolo_confidence,verbose=False)[0]
                            for b in probe.boxes:
                                name=probe.names[int(b.cls[0])]; conf=float(b.conf[0]); coords=b.xyxy[0].tolist()
                                model_candidates.append(dict(confidence=round(conf,3),box=coords,
                                    **{'class':name,'pass':f'head{probe_size}','crop_origin':[ox,oy]}))
                                category,positive=_category(name)
                                if category=='helmet' and positive and conf>=_ppe_threshold('helmet') and (best_head is None or conf>best_head['confidence']):
                                    best_head=dict(category='helmet',positive=True,confidence=round(conf,3),
                                        **{'class':name,'box':dict(x1=coords[0]+ox,y1=coords[1]+oy,x2=coords[2]+ox,y2=coords[3]+oy),
                                           'source':f'head{probe_size}'})
                        if best_head:
                            detections.append(best_head); ppe_seen['helmet']=True
                    if settings.yolo_head_tight_probe and not ppe_seen.get('helmet'):
                        tx=max(0,int(hx1-hw*.1)); ty=max(0,int(hy1-hh*.1))
                        tight=original[ty:min(original.shape[0],int(hy2+hh*.1)),tx:min(original.shape[1],int(hx2+hw*.1))]
                        if tight.size:
                            probe=model(tight,imgsz=480,conf=settings.yolo_confidence,verbose=False)[0]
                            tight_best=None
                            for b in probe.boxes:
                                name=probe.names[int(b.cls[0])]; conf=float(b.conf[0]); coords=b.xyxy[0].tolist()
                                model_candidates.append(dict(confidence=round(conf,3),box=coords,
                                    **{'class':name,'pass':'head_tight480','crop_origin':[tx,ty]}))
                                category,positive=_category(name)
                                if category=='helmet' and positive and conf>=_ppe_threshold('helmet') and (tight_best is None or conf>tight_best['confidence']):
                                    tight_best=dict(category='helmet',positive=True,confidence=round(conf,3),
                                        **{'class':name,'box':dict(x1=coords[0]+tx,y1=coords[1]+ty,x2=coords[2]+tx,y2=coords[3]+ty),'source':'head_tight480'})
                            if tight_best:
                                detections.append(tight_best); ppe_seen['helmet']=True
        if settings.yolo_full_hand_evidence and detail_enabled and len(person_boxes)==1 and not ppe_seen.get('glove'):
            px1,py1,px2,py2=person_boxes[0][1]
            for c in model_candidates[:]:
                if c['pass']!='full' or c['class'].lower()!='hand' or c['confidence']<_ppe_threshold('glove'):
                    continue
                x1,y1,x2,y2=c['box']
                if not (px1-(px2-px1)*.2 <= (x1+x2)/2 <= px2+(px2-px1)*.2 and py1 <= (y1+y2)/2 <= py2):
                    continue
                roi=corrected_image[max(0,int(y1)):min(corrected_image.shape[0],int(y2)),max(0,int(x1)):min(corrected_image.shape[1],int(x2))]
                if not roi.size:continue
                hsv=cv2.cvtColor(roi,cv2.COLOR_BGR2HSV)
                hue,saturation,value=cv2.split(hsv)
                ratio=float((((hue<12)|(hue>168))&(saturation>75)&(value>45)).mean())
                model_candidates.append(dict(c,**{'pass':'full_hand_color','red_pixel_ratio':round(ratio,3)}))
                if ratio>=.35:
                    detections.append(dict(category='glove',positive=True,confidence=c['confidence'],
                        **{'class':'red_work_glove','source':'full_hand_color','red_pixel_ratio':round(ratio,3),
                           'box':dict(x1=x1,y1=y1,x2=x2,y2=y2)}))
                    ppe_seen['glove']=True
                    break
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
        if detail_enabled:
            # Draw boxes on this exact detail frame, never on a newer fast frame.
            image = preview_image(source_image)
            for detection in detections:
                box = detection.get('box')
                if not box:
                    continue
                category = detection.get('category', detection.get('class', 'object'))
                positive = detection.get('positive', True)
                color = colors.get(category, (60, 220, 80)) if positive else (60, 60, 230)
                x1, y1 = max(0, int(box['x1'])), max(0, int(box['y1']))
                x2, y2 = min(image.shape[1]-1, int(box['x2'])), min(image.shape[0]-1, int(box['y2']))
                label = f"{category} {detection.get('confidence', 0):.2f}"
                if detection.get('red_pixel_ratio') is not None:
                    label += ' color-assisted'
                cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
                cv2.putText(image, label, (x1, max(18, y1-6)), cv2.FONT_HERSHEY_SIMPLEX, .5, color, 2)
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
            "engine": getattr(model,'_hanmir_engine','pytorch_cpu'),
            "detections": detections,
            "model_candidates": model_candidates,
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
            "head_probe_attempted": head_probe_attempted,
            "cpu_threads": __import__('torch').get_num_threads(),
            "brightness_gamma": settings.camera_display_gamma,
            "full_input": "original",
            "detail_input": "brightness_corrected",
            "decode_correct_ms": round(decode_ms,3),
            "worker_total_ms": round((time.perf_counter()-worker_started)*1000,3),
            "model_pass_timings": list(getattr(model,'timings',[])),
            "full_model_ms": result.speed,
            "sharpen_amount": settings.camera_sharpen_amount,
            "ppe_crop_attempted": ppe_crop_attempted,
            "source": filename,
            # The normal fast path keeps the latest annotated frame in memory.
            # The router writes evidence to disk only when a safety state
            # actually needs a durable event record.
            "annotated_source": None,
            "_annotated_jpeg": annotated_jpeg,
        }
    except Exception as exc:
        if getattr(model,'_hanmir_engine','')=='openvino_gpu_fp32' and not _fast_gpu_failed:
            logger.exception('GPU inference failed; retrying this frame with original model')
            _fast_gpu_failed=True; _model=None; _model_attempted=False
            return analyze_frame(filename,detail_enabled)
        logger.exception("YOLO 프레임 분석 실패: %s", exc)
        return analyze_frame_dummy(filename)
