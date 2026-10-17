import asyncio
import json
import logging
import re
from datetime import timedelta

from sqlalchemy.orm import Session

from ..database import SessionLocal, utcnow
from ..models.entities import Device, Event, FallDetection, FallIncident, WorkerState
from ..websocket import manager
from .event_service import create_event, event_to_dict
from .risk_service import recalculate_risk
from .tts_generator_service import generate_tts

logger = logging.getLogger(__name__)
PROMPT = "낙상이 의심됩니다. 괜찮으면 ‘괜찮습니다’, 도움이 필요하면 ‘도와주세요’라고 말씀해 주세요."
WEARER = {
    "help": "구조 요청을 관리자에게 전달합니다.",
    "unavailable": "응답이 확인되지 않아 관리자에게 긴급 알림을 보냅니다.",
    "safe": "응답이 확인되었습니다.",
}
ADMIN = {
    "waiting": "낙상 의심 감지, 응답 확인 중…",
    "help": "낙상 의심 감지, 착용자 구조 요청",
    "unavailable": "낙상 의심 감지, 응답 확인 불가",
    "safe": "응답 확인 완료, 낙상 의심 해제",
}
LABELS = {"waiting_prompt": "응답 대기", "waiting_response": "응답 대기",
          "emergency": "긴급", "cleared": "의심 해제"}
tasks = set()


def launch(coroutine):
    task = asyncio.create_task(coroutine)
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    return task


def snapshot(db: Session, incident: FallIncident) -> dict:
    event = db.get(Event, incident.incident_id)
    details = json.loads(event.details_json)
    return {"incident_id": incident.incident_id, "site_id": incident.site_id,
            "device_id": incident.device_id, "worker_id": incident.worker_id,
            "state": incident.state, "state_label": LABELS[incident.state],
            "message": event.message, "wearer_message": details["wearer_message"],
            "audio_url": incident.prompt_url if incident.state == "waiting_prompt" else incident.result_url,
            "result_ready": incident.result_ready,
            "deadline": incident.deadline.isoformat() + "Z", "event": event_to_dict(event)}


async def publish(db: Session, incident: FallIncident, notify: bool):
    data = snapshot(db, incident)
    data["notify"] = notify
    await manager.broadcast("fall_incident", data, site_id=incident.site_id)


def history(event: Event, state: str, reason: str, **extra):
    details = json.loads(event.details_json)
    details.update({"fall_state": state, "state_label": LABELS[state]})
    details["history"].append({"at": utcnow().isoformat() + "Z", "state": state,
                               "reason": reason, **extra})
    event.details_json = json.dumps(details, ensure_ascii=False)


async def finish(db: Session, incident: FallIncident, outcome: str, reason: str, text: str = ""):
    db.refresh(incident)
    if incident.state not in {"waiting_prompt", "waiting_response"}:
        return
    incident.state = "cleared" if outcome == "safe" else "emergency"
    incident.stt_until = None
    event = db.get(Event, incident.incident_id)
    event.message = ADMIN[outcome]
    event.severity = "info" if outcome == "safe" else "emergency"
    event.status = "resolved" if outcome == "safe" else "open"
    history(event, incident.state, reason, transcript=text)
    details = json.loads(event.details_json)
    details.update({"wearer_message": WEARER[outcome], "outcome": outcome})
    event.details_json = json.dumps(details, ensure_ascii=False)
    db.flush()
    worker = db.get(WorkerState, incident.worker_id)
    if worker:
        hazards = json.loads(worker.hazard_json or "{}")
        if incident.state == "emergency":
            hazards["fall_emergency"] = True
            worker.hazard_json = json.dumps(hazards, ensure_ascii=False)
            recalculate_risk(db, worker)
    db.commit()
    await publish(db, incident, outcome != "safe")
    launch(prepare_audio(incident.incident_id, initial=False))


async def prepare_audio(incident_id: str, initial: bool):
    try:
        with SessionLocal() as db:
            incident = db.get(FallIncident, incident_id)
            if not incident:
                return
            message = PROMPT if initial else json.loads(db.get(Event, incident_id).details_json)["wearer_message"]
        audio = await generate_tts(message)
        with SessionLocal() as db:
            incident = db.get(FallIncident, incident_id)
            if initial and incident.state != "waiting_prompt":
                return
            if audio:
                if initial:
                    incident.prompt_url = f"/tts/{audio.name}"
                else:
                    incident.result_url = f"/tts/{audio.name}"
                    incident.result_ready = True
                db.commit()
            elif initial:
                await finish(db, incident, "unavailable", "prompt_generation_failed")
            else:
                incident.result_ready = True
                db.commit()
    except Exception:
        logger.exception("Fall guidance preparation failed for %s", incident_id)
        with SessionLocal() as db:
            incident = db.get(FallIncident, incident_id)
            if incident:
                if initial:
                    await finish(db, incident, "unavailable", "prompt_generation_failed")
                else:
                    incident.result_ready = True
                    db.commit()


async def detect(db: Session, device: Device, detection_id: str, evidence: dict) -> FallIncident:
    key = f"{device.device_id}:{detection_id}"
    receipt = db.get(FallDetection, key)
    if receipt:
        return db.get(FallIncident, receipt.incident_id)
    existing = db.query(FallIncident).filter(FallIncident.device_id == device.device_id,
        FallIncident.state.in_(["waiting_prompt", "waiting_response", "emergency"])).order_by(FallIncident.created_at.desc()).first()
    if existing and db.get(Event, existing.incident_id).status != "resolved":
        db.add(FallDetection(detection_id=key, incident_id=existing.incident_id))
        event = db.get(Event, existing.incident_id)
        history(event, existing.state, "additional_detection", detection_id=detection_id, evidence=evidence)
        db.commit()
        return existing
    event = create_event(db, "FALL_SUSPECTED", ADMIN["waiting"], "warning", device.worker_id,
                         device.device_id, {"wearer_message": PROMPT, "history": [], "evidence": evidence}, device.site_id)
    incident = FallIncident(incident_id=event.event_id, device_id=device.device_id,
        worker_id=device.worker_id, site_id=device.site_id, detection_id=key,
        state="waiting_prompt", deadline=utcnow() + timedelta(seconds=30))
    db.add(incident)
    db.add(FallDetection(detection_id=key, incident_id=incident.incident_id))
    history(event, incident.state, "imu_detection")
    db.commit()
    await publish(db, incident, True)
    launch(prepare_audio(incident.incident_id, initial=True))
    return incident


async def playback(db: Session, incident: FallIncident, ok: bool, remaining_ms: int):
    if incident.state != "waiting_prompt":
        return
    if not ok:
        await finish(db, incident, "unavailable", "prompt_playback_failed")
        return
    incident.state = "waiting_response"
    incident.deadline = utcnow() + timedelta(milliseconds=min(8000, max(0, remaining_ms)))
    history(db.get(Event, incident.incident_id), incident.state, "prompt_playback_finished")
    db.commit()
    await publish(db, incident, False)


def classify(text: str) -> str | None:
    normalized = re.sub(r"[\s.,!?。！？‘’\"']", "", text)
    if normalized == "도와주세요":
        return "help"
    if normalized == "괜찮습니다":
        return "safe"
    return None


async def expire(db: Session):
    now = utcnow()
    rows = db.query(FallIncident).filter(FallIncident.state.in_(["waiting_prompt", "waiting_response"]),
                                         FallIncident.deadline <= now).all()
    for incident in rows:
        if not incident.stt_until or incident.stt_until <= now:
            await finish(db, incident, "unavailable", "response_timeout" if incident.state == "waiting_response" else "prompt_delivery_timeout")


async def run_timeouts():
    while True:
        try:
            with SessionLocal() as db:
                await expire(db)
        except Exception:
            logger.exception("Fall timeout processing failed")
        await asyncio.sleep(0.2)
