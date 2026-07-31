from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db, utcnow
from ..models.entities import Device, VoiceCommand, WorkerState
from ..schemas.api import MockCommandIn
from ..services.assistant_service import build_response
from ..services.audio_service import dummy_stt, save_audio
from ..services.event_service import create_event, event_to_dict
from ..services.risk_service import recalculate_risk
from ..services.serializers import worker_to_dict
from ..services.speech_service import normalize, resolve_intent
from ..websocket import manager

router = APIRouter(prefix="/api/audio", tags=["audio"])


async def process_text(db: Session, worker_id: str, device_id: str, text: str) -> dict:
    worker = db.get(WorkerState, worker_id)
    if not worker:
        raise HTTPException(404, "작업자를 찾을 수 없습니다.")
    intent, confidence = resolve_intent(text)
    command = VoiceCommand(
        worker_id=worker_id,
        device_id=device_id,
        original_text=text,
        normalized_text=normalize(text),
        intent=intent,
        confidence=confidence,
    )
    db.add(command)
    if intent in ("emergency", "help"):
        worker.emergency = True
    recalculate_risk(db, worker)
    message, speaker_command = build_response(intent, worker_to_dict(worker))
    event = create_event(
        db,
        "VOICE_COMMAND",
        f"음성 명령: {text} → {intent}",
        "emergency" if intent == "emergency" else "info",
        worker_id,
        device_id,
        {"text": text, "intent": intent, "confidence": confidence, "response": message, "speaker_command": speaker_command},
    )
    db.flush()
    return {"command_id": command.id, "text": text, "intent": intent, "confidence": confidence, "response": message, "speaker_command": speaker_command, "event": event_to_dict(event), "worker": worker_to_dict(worker)}


@router.post("/upload")
async def upload_audio(
    file: UploadFile = File(...),
    device_id: str = Form(...),
    worker_id: str = Form(...),
    db: Session = Depends(get_db),
):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "먼저 장치를 등록하세요.")
    path = await save_audio(file, device_id)
    device.last_audio_at = utcnow()
    result = await process_text(db, worker_id, device_id, dummy_stt(path))
    db.commit()
    await manager.broadcast("voice_command", result)
    return result


@router.post("/mock-command")
async def mock_command(payload: MockCommandIn, db: Session = Depends(get_db)):
    result = await process_text(db, payload.worker_id, payload.device_id, payload.text)
    device = db.get(Device, payload.device_id)
    if device:
        device.last_audio_at = utcnow()
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

