import asyncio
import json
import logging
from datetime import timedelta
from time import perf_counter

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db, utcnow
from ..models.entities import Device, VoiceCommand, WorkerState
from ..schemas.api import TextCommandIn
from ..services.assistant_service import build_response_smart, is_explanation_request
from ..services.device_service import mark_device_seen
from ..services.audio_service import save_audio, stt
from ..services.voice_trace import record_voice
from ..services.camera_trace import record_analysis
from ..services.command_service import queue_command
from ..services.event_service import create_event, event_to_dict
from ..services.evacuation_service import calculate_route, current_incident, evacuation_snapshot, trigger_fire, activate_voice_fire
from ..services.risk_service import recalculate_risk
from ..services.safety_agent_service import build_safety_action_plan
from ..services.serializers import worker_to_dict
from ..services.speech_service import normalize, resolve_intent
from ..services.tts_generator_service import generate_tts
from ..services.voice_execution_gate import voice_execution_gate
from ..services.wake_word_service import WakeDecision, wake_word_gate
from ..services.inference_priority import voice_priority
from ..websocket import call_manager, manager
from .auth import require_site

router = APIRouter(prefix="/api/audio", tags=["audio"])
logger = logging.getLogger(__name__)


async def _commit(db: Session) -> None:
    # The request alone owns this Session; wait before touching it again.
    # Shield the thread so dependency cleanup cannot close it during a commit.
    started = perf_counter()
    task = asyncio.create_task(asyncio.to_thread(db.commit))
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        try:
            await task
        finally:
            raise
    finally:
        if settings.yolo_trace_enabled:
            record_analysis(lane="voice_db_commit", elapsed_ms=round((perf_counter()-started)*1000, 2))


def _prune_audio(path):
    try:
        if settings.voice_trace_retain_audio:
            retained = sorted(path.parent.glob("helmet-*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
            for old in retained[settings.voice_trace_audio_files:]:
                old.unlink(missing_ok=True)
        else:
            path.unlink(missing_ok=True)
    except OSError:
        pass


async def process_text(
    db: Session,
    worker_id: str,
    device_id: str,
    text: str,
    sound_db: float | None = None,
    allow_retry: bool = True,
) -> dict:
    worker = db.get(WorkerState, worker_id)
    if not worker:
        raise HTTPException(404, "작업자를 찾을 수 없습니다.")
    intent, confidence = resolve_intent(text)
    # A quiet emergency must still be accepted. sound_db is diagnostic input,
    # not a condition for discarding an explicit SOS or fire report.
    command = VoiceCommand(
        worker_id=worker_id,
        site_id=worker.site_id,
        device_id=device_id,
        original_text=text,
        normalized_text=normalize(text),
        intent=intent,
        confidence=confidence,
    )
    db.add(command)
    evacuation_created = False
    if intent in {"fire_report", "fire_confirm"}:
        hazards = json.loads(worker.hazard_json or "{}")
        hazards.update({"fire": True, "fire_reported": True})
        worker.hazard_json = json.dumps(hazards, ensure_ascii=False)
        _, evacuation_created = activate_voice_fire(db, worker_id, text, intent == "fire_confirm")
    if intent in ("emergency", "help"):
        worker.emergency = True
    recalculate_risk(db, worker)
    worker_data = worker_to_dict(worker)
    devices = db.query(Device).filter(Device.worker_id == worker_id).all()
    cutoff = utcnow() - timedelta(seconds=settings.device_offline_seconds)
    live = [device for device in devices if device.online and device.last_seen and device.last_seen >= cutoff]
    worker_data["data_freshness"] = {
        "location": any(device.last_uwb_at and device.last_uwb_at >= cutoff for device in live),
        "vision": any(device.last_camera_at and device.last_camera_at >= cutoff for device in live),
        "device": bool(live),
    }
    av = next((device for device in live if device.device_id == device_id), None)
    worker_data["battery"] = av.battery if av else None
    incident = current_incident(db, worker.site_id)
    live_fire_route = None
    if incident:
        from ..services.evacuation_navigation import latest_route, navigation_step, map_signature
        if intent in {"fire_report", "fire_confirm"} and json.loads(incident.details_json or "{}").get("navigation_enabled"):
            _, live_fire_route = navigation_step(db, worker, incident, map_signature(db, worker.site_id))
        worker_data["evacuation"] = live_fire_route or latest_route(worker.worker_id) or calculate_route(db, worker, incident)
    agent_plan = build_safety_action_plan(intent, worker_data, text)

    # 위험 상태를 먼저 저장해 외부 AI/TTS 대기 중 SQLite 쓰기 잠금을 잡지 않는다.
    await _commit(db)

    if intent == "stop_speaking":
        await manager.send_device_command(device_id, {"command_type": "stop_alert", "payload": {}})
    if intent == "hang_up":
        await call_manager.end_call(device_id)

    # 명령을 이해한 즉시 짧은 성공음을 내어, TTS 생성 중에도 작업자가 인식 성공을 알 수 있게 한다.
    feedback_delivered = 0
    feedback_command_id = None
    if intent not in {"unknown", "stop_speaking", "hang_up", "fire_report", "fire_confirm"}:
        feedback_payload = {"frequency": 1850, "duration": 110, "purpose": "intent_recognized"}
        feedback = queue_command(db, device_id, "play_tone", feedback_payload)
        feedback_command_id = feedback.command_id
        await _commit(db)
        feedback_delivered = await manager.send_device_command(
            device_id,
            {
                "command_id": feedback.command_id,
                "command_type": "play_tone",
                "payload": feedback_payload,
            },
        )
        feedback.status = "delivered" if feedback_delivered else "queued"

    complex_request = intent == "unknown" and is_explanation_request(text)
    terminal_unknown = intent == "unknown" and not allow_retry and not complex_request
    response_started = perf_counter()
    fire_delivery = None
    if live_fire_route:
        from ..services.evacuation_guidance_service import send_helmet_guidance
        prefix = "화재가 확정됐습니다. " if intent == "fire_confirm" else "화재 신고를 접수했습니다. "
        first_route = dict(live_fire_route)
        fire_delivery = await send_helmet_guidance(worker_id, device_id, incident.incident_id, first_route, force=True)
        message, speaker_command = prefix + first_route["message"], None
    elif terminal_unknown or intent in {"stop_speaking", "hang_up"}:
        message, speaker_command = "", None
    else:
        message, speaker_command = await build_response_smart(intent, worker_data, text)
    response_done = perf_counter()
    audio_path = await generate_tts(message) if message and not live_fire_route else None
    tts_done = perf_counter()
    audio_url = f"/tts/{audio_path.name}" if audio_path else None
    if audio_url and speaker_command:
        speaker_command = "play_audio"

    # Only an unrecognized command gets a second listening turn.  A normal
    # response must not re-open the microphone, because ambient speech could
    # otherwise be processed as a command.
    listen_again = intent == "unknown" and allow_retry and not complex_request
    if listen_again:
        wake_word_gate.arm(device_id)

    delivered = int(bool(fire_delivery and fire_delivery.get("sent")))
    device_command_id = None
    if speaker_command:
        speaker_payload = {
            "message": message,
            "audio_url": audio_url,
            "listen_again": listen_again,
            "start_call_ringing": agent_plan["start_manager_call"],
        }
        record = queue_command(db, device_id, speaker_command, speaker_payload)
        device_command_id = record.command_id
        await _commit(db)
        delivered = await manager.send_device_command(
            device_id,
            {"command_id": record.command_id, "command_type": speaker_command, "payload": speaker_payload},
        )
        record.status = "delivered" if delivered else "queued"

    event = create_event(
        db,
        "VOICE_COMMAND",
        f"음성 명령: {text} → {intent}",
        "emergency" if intent in ("emergency", "help", "fire_report", "fire_confirm") else "info",
        worker_id,
        device_id,
        {
            "text": text,
            "intent": intent,
            "confidence": confidence,
            "sound_db": sound_db,
            "response": message,
            "speaker_command": speaker_command,
            "audio_url": audio_url,
            "device_command_id": device_command_id,
            "delivered_connections": delivered,
            "feedback_command_id": feedback_command_id,
            "feedback_delivered_connections": feedback_delivered,
            "evacuation_created": evacuation_created,
            "evacuation_guidance": fire_delivery,
            "safety_agent": agent_plan,
        },
    )
    db.flush()
    if agent_plan["start_manager_call"]:
        # Commit before the detached timeout task opens its own DB session.
        await _commit(db)
        await call_manager.begin_call_request(device_id, worker_id, event.event_id)
    return {
        "command_id": command.id,
        "text": text,
        "intent": intent,
        "confidence": confidence,
        "response": message,
        "speaker_command": speaker_command,
        "audio_url": audio_url,
        "delivered_connections": delivered,
        "feedback_command_id": feedback_command_id,
        "feedback_delivered_connections": feedback_delivered,
        "event": event_to_dict(event),
        "worker": worker_to_dict(worker),
        "safety_agent": agent_plan,
        "evacuation": evacuation_snapshot(db, worker.site_id),
        "timings_ms": {
            "response": round((response_done - response_started) * 1000, 1),
            "tts": round((tts_done - response_done) * 1000, 1),
        },
    }


@router.post("/upload")
async def upload_audio(
    file: UploadFile = File(...),
    device_id: str = Form(...),
    worker_id: str = Form(...),
    sound_db: float | None = Form(None),
    wake_detected: bool = Form(False),
    db: Session = Depends(get_db),
    _voice_priority: None = Depends(voice_priority),
):
    received_at = perf_counter()
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "먼저 장치를 등록하세요.")
    path = await save_audio(file, device_id)
    saved_at = perf_counter()
    mark_device_seen(device, "audio")
    from ..services.fall_confirmation import awaiting_reply
    transcript = await stt(path, command_only=wake_detected, confirmation_mode=awaiting_reply(device_id))
    stt_done = perf_counter()
    from ..services.fall_confirmation import accept_reply
    fall_reply=accept_reply(device_id,transcript)
    if fall_reply:
        await _commit(db)
        await asyncio.to_thread(_prune_audio,path)
        fall_reply['timings_ms']={'stt':round((stt_done-saved_at)*1000,1),'total_server':round((perf_counter()-received_at)*1000,1)}
        record_voice('response',path.name,**fall_reply)
        return fall_reply
    await asyncio.to_thread(_prune_audio, path)

    if wake_detected:
        decision = (
            WakeDecision("command", transcript, transcript, "device_wake")
            if transcript else WakeDecision("ignored", transcript, reason="stt_empty_after_device_wake")
        )
    else:
        decision = wake_word_gate.evaluate(device_id, transcript)
    record_voice("wake_decision", path.name, device_id=device_id, worker_id=worker_id,
                 status=decision.status, reason=decision.reason, transcript=decision.transcript[:2000],
                 stt_ms=round((stt_done-saved_at)*1000, 1))
    if decision.status != "command":
        acknowledgement = None
        audio_url = None
        delivered = 0
        device_command_id = None

        if decision.status == "armed":
            acknowledgement = "네, 말씀하세요."
            audio_path = await generate_tts(acknowledgement)
            audio_url = f"/tts/{audio_path.name}" if audio_path else None
            command_type = "play_audio" if audio_url else "play_ack"
            payload = {
                "message": acknowledgement,
                "audio_url": audio_url,
                "local_asset": "acknowledgement",
            }
            record = queue_command(db, device_id, command_type, payload)
            device_command_id = record.command_id
            await _commit(db)
            delivered = await manager.send_device_command(
                device_id,
                {
                    "command_id": record.command_id,
                    "command_type": command_type,
                    "payload": payload,
                },
            )
            record.status = "delivered" if delivered else "queued"

        await _commit(db)
        result = {
            "status": decision.status,
            "text": decision.transcript,
            "reason": decision.reason,
            "wake_word": "투투스",
            "followup_seconds": settings.wake_followup_seconds if decision.status == "armed" else 0,
            "acknowledgement": acknowledgement,
            "audio_url": audio_url,
            "device_command_id": device_command_id,
            "delivered_connections": delivered,
        }
        result["timings_ms"] = {
            "save": round((saved_at - received_at) * 1000, 1),
            "stt": round((stt_done - saved_at) * 1000, 1),
            "total_server": round((perf_counter() - received_at) * 1000, 1),
        }
        logger.info("voice_pipeline status=%s reason=%s timings_ms=%s", decision.status, decision.reason, result["timings_ms"])
        record_voice("response", path.name, status=decision.status, delivered_connections=delivered,
                     command_id=device_command_id, timings_ms=result["timings_ms"])
        return result

    allowed, execution_reason = voice_execution_gate.allow(device_id, decision.command_text)
    if not allowed:
        record_voice("execution_gate", path.name, status="ignored", reason=execution_reason)
        await _commit(db)
        return {
            "status": "ignored",
            "text": decision.transcript,
            "reason": execution_reason,
            "wake_word": "투투스",
            "followup_seconds": 0,
            "delivered_connections": 0,
        }

    retry_followup = decision.reason in {"retry_followup", "retry_followup_empty"}
    result = await process_text(
        db,
        worker_id,
        device_id,
        decision.command_text,
        sound_db,
        allow_retry=not retry_followup,
    )
    result["status"] = "command"
    result["transcript"] = decision.transcript
    result["wake_reason"] = decision.reason
    result["timings_ms"].update({
        "save": round((saved_at - received_at) * 1000, 1),
        "stt": round((stt_done - saved_at) * 1000, 1),
        "total_server": round((perf_counter() - received_at) * 1000, 1),
    })
    logger.info("voice_pipeline status=command reason=%s timings_ms=%s", decision.reason, result["timings_ms"])
    record_voice("response", path.name, status="command", intent=result.get("intent"),
                 delivered_connections=result.get("delivered_connections"), timings_ms=result["timings_ms"])
    await _commit(db)
    await manager.broadcast("voice_command", result)
    return result


@router.post("/command")
async def text_command(
    payload: TextCommandIn,
    site_id: str = Depends(require_site),
    db: Session = Depends(get_db),
    _voice_priority: None = Depends(voice_priority),
):
    device = db.get(Device, payload.device_id)
    worker = db.get(WorkerState, payload.worker_id)
    if not device or device.site_id != site_id or not worker or worker.site_id != site_id:
        raise HTTPException(404, "선택한 안전모 장치가 등록되지 않았습니다.")
    result = await process_text(db, payload.worker_id, payload.device_id, payload.text, payload.sound_db)
    await _commit(db)
    await manager.broadcast("voice_command", result)
    return result


@router.get("/commands")
def list_commands(limit: int = 50, site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    rows = db.query(VoiceCommand).filter(VoiceCommand.site_id == site_id).order_by(VoiceCommand.created_at.desc()).limit(min(limit, 200)).all()
    return [
        {
            "id": row.id,
            "worker_id": row.worker_id,
            "device_id": row.device_id,
            "text": row.original_text,
            "intent": row.intent,
            "confidence": row.confidence,
            "created_at": row.created_at.isoformat() + "Z",
        }
        for row in rows
    ]






