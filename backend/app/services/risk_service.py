from datetime import datetime
import json
import math

from sqlalchemy.orm import Session

from ..database import utcnow
from ..models.entities import Device, WorkerState, Zone


ROLE_LABELS = {
    "general_worker": "일반작업자",
    "manager": "관리자",
    "hot_work_authorized": "화기인가자",
    "heavy_equipment_operator": "중장비운전자",
    "unauthorized": "비인가자",
}


def risk_level(score: int) -> str:
    if score >= 80:
        return "비상"
    if score >= 60:
        return "위험"
    if score >= 40:
        return "주의"
    if score >= 20:
        return "관심"
    return "정상"


def _decision(priority: int, code: str, reason: str, points: int, voice: str, action: str, **evidence) -> dict:
    return {
        "priority": priority,
        "code": code,
        "reason": reason,
        "points": points,
        "web_message": reason,
        "voice_message": voice,
        "action": action,
        "evidence": evidence,
    }


def _night() -> bool:
    hour = datetime.now().hour
    return hour >= 18 or hour < 6


def _zone(db: Session, worker: WorkerState) -> Zone | None:
    return db.get(Zone, worker.current_zone) if worker.current_zone else None


def _uwb_loss_seconds(devices: list[Device]) -> float | None:
    stamps = [item.last_uwb_at for item in devices if item.device_type == "position_device" and item.last_uwb_at]
    if not stamps:
        return None
    return max(0.0, (utcnow() - max(stamps)).total_seconds())


def _crowded(db: Session, worker: WorkerState) -> bool:
    return sum(math.hypot(item.x - worker.x, item.y - worker.y) <= 2.0 for item in db.query(WorkerState).all()) >= 5


def evaluate_risk(db: Session, worker: WorkerState) -> dict:
    ppe = json.loads(worker.ppe_json or "{}")
    hazards = json.loads(worker.hazard_json or "{}")
    zone = _zone(db, worker)
    category = zone.zone_category if zone else "general"
    role = worker.worker_role or "general_worker"
    devices = db.query(Device).filter(Device.worker_id == worker.worker_id).all()
    loss_seconds = _uwb_loss_seconds(devices)

    if hazards.get("fire_reported"):
        return _decision(1, "REPORTED_FIRE", "작업자 화재 발생 신고", 100, "화재 신고가 접수되었습니다. 기본 대피경로를 따라 즉시 대피하세요.", "SIREN_SOS_EVACUATE")
    if worker.emergency:
        return _decision(1, "LIFE_EMERGENCY", "긴급 구조 요청", 100, "긴급 구조 요청 접수 완료. 즉시 대피하십시오.", "SOS_AND_EVACUATE")
    if hazards.get("large_fire") or float(hazards.get("fire_area_ratio") or 0) >= 0.15 or float(hazards.get("fire_expansion_rate") or 0) >= 0.20:
        return _decision(1, "LARGE_FIRE", "대형 화재", 100, "대형 화재가 발생했습니다. 하던 일을 멈추고 즉시 대피하세요.", "SIREN_SOS_EVACUATE", fire_area_ratio=hazards.get("fire_area_ratio"))
    if hazards.get("fallen") or hazards.get("man_down"):
        return _decision(1, "MAN_DOWN", "부상자 발견", 95, "부상자가 발견되었습니다. 구조대 호출 완료.", "SOS_RESCUE")
    if hazards.get("smoke") and category == "confined":
        return _decision(1, "CONFINED_GAS", "유독가스 누출", 100, "밀폐공간 유독가스 누출. 호흡 보호구를 착용하고 즉시 이탈하세요.", "SIREN_SOS_EVACUATE")
    if loss_seconds is not None and (loss_seconds >= 600 or (category == "confined" and loss_seconds >= 60)):
        return _decision(1, "LAST_KNOWN_SOS", "최후 좌표 SOS", 100, "통신이 장시간 끊겼습니다. 구조 요청을 전송합니다.", "LAST_POSITION_SOS", loss_seconds=round(loss_seconds))

    if hazards.get("fire"):
        permitted = role == "hot_work_authorized" and category in {"general", "danger"} and not _night()
        if permitted:
            return _decision(5, "AUTHORIZED_HOT_WORK", "인가된 화기 작업", 0, "", "BYPASS")
        if category == "confined":
            return _decision(2, "CONFINED_HOT_WORK", "폭발 위험(화기)", 85, "밀폐공간 내 화기 취급입니다. 즉시 불을 끄고 이탈하세요.", "STOP_WORK_AND_EVACUATE")
        if category == "controlled":
            return _decision(2, "CONTROLLED_ZONE_FIRE", "보안구역 화재", 80, "통제구역 내 화기 취급이 감지되었습니다. 즉시 작업을 중지하세요.", "STOP_WORK_SECURITY_ALERT")
        return _decision(2, "UNAUTHORIZED_HOT_WORK", "미인가 화기 취급", 75, "허가되지 않은 화기 취급입니다. 즉시 작업을 중지하세요.", "STOP_WORK")
    if hazards.get("smoke"):
        return _decision(2, "SMOKE", "화재 징후(연기)", 70, "연기가 감지되었습니다. 안전한 장소로 이동하고 현장을 확인하세요.", "WARN_AND_INSPECT")

    if worker.current_zone and not (role == "manager" and category == "controlled"):
        label = "통제구역 침입" if category == "controlled" else "위험구역 진입"
        return _decision(3, "ZONE_ACCESS_VIOLATION", label, max(60, zone.risk_weight if zone else 60), "출입 권한이 없는 구역입니다. 즉시 이탈하세요.", "LEAVE_ZONE", zone_id=worker.current_zone, zone_category=category)
    if _crowded(db, worker):
        return _decision(3, "CROWDING", "인원 과밀집", 60, "반경 2미터 이내 인원이 과밀합니다. 즉시 분산하세요.", "DISPERSE")
    if loss_seconds is not None and loss_seconds >= 60:
        return _decision(3, "UWB_SIGNAL_LOSS", "통신 두절 경고", 60, "통신 연결이 불안정합니다. 안전구역으로 이동하세요.", "RETURN_TO_COVERAGE", loss_seconds=round(loss_seconds))

    if category not in {"safe", "rest"}:
        if ppe.get("helmet") is False:
            return _decision(4, "PPE_HELMET", "안전모 미착용", 40, "전방 작업자에게 안전모 착용을 지시하세요.", "CORRECT_PPE")
        if ppe.get("vest") is False:
            voice = "야간 시인성 확보를 위해 전방 작업자에게 안전조끼 착용을 지시하세요." if _night() else "전방 작업자에게 안전조끼 착용을 지시하세요."
            return _decision(4, "PPE_VEST", "조끼 미착용", 30, voice, "CORRECT_PPE")
        if ppe.get("glove") is False:
            return _decision(4, "PPE_GLOVE", "장갑 미착용", 20, "작업 전 안전장갑 착용을 확인하세요.", "CORRECT_PPE")

    if worker.confidence < 0.45:
        return _decision(4, "LOW_POSITION_CONFIDENCE", "위치 신뢰도 낮음", 20, "위치 신호가 불안정합니다. 앵커 가시성을 확인하세요.", "CHECK_UWB")
    if any((item.battery is not None and item.battery <= 15) for item in devices):
        return _decision(4, "LOW_BATTERY", "배터리 15% 이하", 20, "안전모 배터리가 부족합니다. 충전 또는 교체하세요.", "CHARGE_DEVICE")

    return _decision(5, "SAFE", "정상", 0, "", "NONE")


def recalculate_risk(db: Session, worker: WorkerState) -> WorkerState:
    result = evaluate_risk(db, worker)
    worker.risk_score = min(100, int(result["points"]))
    worker.risk_level = risk_level(worker.risk_score)
    worker.reasons_json = json.dumps([result], ensure_ascii=False)
    db.flush()
    return worker

