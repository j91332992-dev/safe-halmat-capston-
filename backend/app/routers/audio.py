import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db, utcnow
from ..models.entities import Device, VoiceCommand, WorkerState
from ..schemas.api import TextCommandIn
from ..services.assistant_service import build_response_smart
from ..services.device_service import mark_device_seen
from ..services.audio_service import save_audio, stt
from ..services.command_service import queue_command
from ..services.event_service import create_event, event_to_dict
from ..services.evacuation_service import calculate_route, current_incident, evacuation_snapshot, trigger_fire
from ..services.risk_service import recalculate_risk
from ..services.serializers import worker_to_dict
from ..services.speech_service import normalize, resolve_intent
from ..services.tts_generator_service import generate_tts
from ..services.wake_word_service import wake_word_gate
from ..websocket import manager

router = APIRouter(prefix="/api/audio", tags=["audio"])


async def process_text(db: Session, worker_id: str, device_id: str, text: str, sound_db: float | None = None) -> dict:
    worker = db.get(WorkerState, worker_id)
    if not worker:
        raise HTTPException(404, "작업자를 찾을 수 없습니다.")
    intent, confidence = resolve_intent(text)
    if intent in ("emergency", "help", "fire_report") and sound_db is not None and sound_db < 80:
        intent, confidence = "unknown", 0.0
    command = VoiceCommand(
        worker_id=worker_id,
        device_id=device_id,
        original_text=text,
        normalized_text=normalize(text),
        intent=intent,
        confidence=confidence,
    )
    db.add(command)
    evacuation_created = False
    if intent == "fire_report":
        hazards = json.loads(worker.hazard_json or "{}")
        hazards.update({"fire": True, "fire_reported": True})
        worker.hazard_json = json.dumps(hazards, ensure_ascii=False)
        _, evacuation_created = trigger_fire(db, "voice", worker_id, {"text": text, "sound_db": sound_db})
    if intent in ("emergency", "help"):
        worker.emergency = True
    recalculate_risk(db, worker)
    worker_data = worker_to_dict(worker)
    incident = current_incident(db)
    if incident:
        worker_data["evacuation"] = calculate_route(db, worker, incident)
    message, speaker_command = await build_response_smart(intent, worker_data)
    audio_path = await generate_tts(message)
    audio_url = f"/tts/{audio_path.name}" if audio_path else None
    if audio_url and speaker_command:
        speaker_command = "play_audio"

    delivered = 0
    device_command_id = None
    if speaker_command:
        record = queue_command(db, device_id, speaker_command, {"message": message, "audio_url": audio_url})
        device_command_id = record.command_id
        delivered = await manager.send_device_command(
            device_id,
            {"command_id": record.command_id, "command_type": speaker_command, "payload": {"message": message, "audio_url": audio_url}},
        )
        record.status = "delivered" if delivered else "queued"

    event = create_event(
        db,
        "VOICE_COMMAND",
        f"음성 명령: {text} → {intent}",
        "emergency" if intent in ("emergency", "help", "fire_report") else "info",
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
            "evacuation_created": evacuation_created,
        },
    )
    db.flush()
    return {
        "command_id": command.id,
        "text": text,
        "intent": intent,
        "confidence": confidence,
        "response": message,
        "speaker_command": speaker_command,
        "audio_url": audio_url,
        "delivered_connections": delivered,
        "event": event_to_dict(event),
        "worker": worker_to_dict(worker),
        "evacuation": evacuation_snapshot(db) if current_incident(db) else {"incident": None, "routes": {}},
    }


@router.post("/upload")
async def upload_audio(
    file: UploadFile = File(...),
    device_id: str = Form(...),
    worker_id: str = Form(...),
    sound_db: float | None = Form(None),
    db: Session = Depends(get_db),
):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "먼저 장치를 등록하세요.")
    path = await save_audio(file, device_id)
    mark_device_seen(device, "audio")
    transcript = await stt(path)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass

    decision = wake_word_gate.evaluate(device_id, transcript)
    if decision.status != "command":
        acknowledgement = None
        audio_url = None
        delivered = 0
        device_command_id = None

        if decision.status == "armed":
            acknowledgement = "네, 말씀하세요."
            audio_path = await generate_tts(acknowledgement)
            audio_url = f"/tts/{audio_path.name}" if audio_path else None
            command_type = "play_audio" if audio_url else "play_tone"
            payload = {
                "message": acknowledgement,
                "audio_url": audio_url,
                "frequency": 1200,
                "duration": 180,
            }
            record = queue_command(db, device_id, command_type, payload)
            device_command_id = record.command_id
            delivered = await manager.send_device_command(
                device_id,
                {
                    "command_id": record.command_id,
                    "command_type": command_type,
                    "payload": payload,
                },
            )
            record.status = "delivered" if delivered else "queued"

        db.commit()
        return {
            "status": decision.status,
            "text": decision.transcript,
            "reason": decision.reason,
            "wake_word": "세이피",
            "followup_seconds": settings.wake_followup_seconds if decision.status == "armed" else 0,
            "acknowledgement": acknowledgement,
            "audio_url": audio_url,
            "device_command_id": device_command_id,
            "delivered_connections": delivered,
        }

    result = await process_text(db, worker_id, device_id, decision.command_text, sound_db)
    result["status"] = "command"
    result["transcript"] = decision.transcript
    result["wake_reason"] = decision.reason
    db.commit()
    await manager.broadcast("voice_command", result)
    return result


@router.post("/command")
async def text_command(payload: TextCommandIn, db: Session = Depends(get_db)):
    if not db.get(Device, payload.device_id):
        raise HTTPException(404, "선택한 안전모 장치가 등록되지 않았습니다.")
    result = await process_text(db, payload.worker_id, payload.device_id, payload.text, payload.sound_db)
    db.commit()
    await manager.broadcast("voice_command", result)
    return result


@router.get("/commands")
def list_commands(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(VoiceCommand).order_by(VoiceCommand.created_at.desc()).limit(min(limit, 200)).all()
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








