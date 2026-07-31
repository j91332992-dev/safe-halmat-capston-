import json

from sqlalchemy.orm import Session

from ..models.entities import Device, WorkerState, Zone


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


def recalculate_risk(db: Session, worker: WorkerState) -> WorkerState:
    ppe = json.loads(worker.ppe_json or "{}")
    hazards = json.loads(worker.hazard_json or "{}")
    reasons: list[dict] = []
    score = 0

    def add(points: int, reason: str) -> None:
        nonlocal score
        score += points
        reasons.append({"reason": reason, "points": points})

    if worker.emergency:
        score = 100
        reasons = [{"reason": "비상 버튼 또는 음성 비상", "points": 100}]
    else:
        if worker.current_zone:
            zone = db.get(Zone, worker.current_zone)
            add(zone.risk_weight if zone else 30, "위험구역 진입")
            if zone:
                required = json.loads(zone.required_ppe_json or "[]")
                if any(not ppe.get(item, False) for item in required):
                    add(25, "위험구역 필수 보호구 미착용")
        if not ppe.get("vest", True):
            add(10, "조끼 미착용")
        if not ppe.get("glove", True):
            add(5, "장갑 미착용")
        if hazards.get("smoke"):
            add(40, "연기 감지")
        if hazards.get("fire"):
            add(50, "화재 감지")
        if worker.confidence < 0.45:
            add(10, "위치 신뢰도 낮음")
        devices = db.query(Device).filter(Device.worker_id == worker.worker_id).all()
        if devices and any(not d.online for d in devices):
            add(10, "장치 오프라인")
        if any((d.battery or 100) <= 15 for d in devices):
            add(10, "배터리 15% 이하")
    worker.risk_score = min(100, score)
    worker.risk_level = risk_level(worker.risk_score)
    worker.reasons_json = json.dumps(reasons, ensure_ascii=False)
    db.flush()
    return worker

