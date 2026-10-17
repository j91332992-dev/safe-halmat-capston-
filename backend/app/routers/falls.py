from datetime import timedelta
from secrets import compare_digest

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db, utcnow
from ..models.entities import Device, Event, FallIncident, WorkerState
from ..services import fall_service as falls
from ..services.audio_service import save_audio, stt
from ..websocket import call_manager

router = APIRouter(prefix="/api/falls", tags=["falls"])


def device_snapshot(db, incident):
    result = falls.snapshot(db, incident)
    result.pop("event")
    return result


def authenticate(authorization: str = Header(default="")):
    expected = settings.call_device_token
    token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
    if not expected or not token or not compare_digest(expected, token):
        raise HTTPException(401, "장치 인증이 필요합니다.")


def device_for(db, device_id):
    device = db.get(Device, device_id)
    worker = db.get(WorkerState, device.worker_id) if device else None
    if not device or device.device_type != "assistant_device" or not worker or worker.site_id != device.site_id:
        raise HTTPException(404, "등록된 안전모와 작업자가 필요합니다.")
    return device


def incident_for(db, incident_id, device_id):
    device_for(db, device_id)
    incident = db.get(FallIncident, incident_id)
    if not incident or incident.device_id != device_id:
        raise HTTPException(404, "낙상 의심 사건을 찾을 수 없습니다.")
    return incident


class Detection(BaseModel):
    device_id: str = Field(max_length=80)
    detection_id: str = Field(min_length=1, max_length=15)
    peak_g: float = Field(ge=0, le=1000, allow_inf_nan=False)
    peak_rad_s: float = Field(ge=0, le=1000, allow_inf_nan=False)
    tilt_deg: float = Field(ge=0, le=180, allow_inf_nan=False)
    call_active: bool = False


class Playback(BaseModel):
    device_id: str
    ok: bool
    remaining_ms: int = Field(default=8000, ge=0, le=8000)


@router.post("/detect", dependencies=[Depends(authenticate)])
async def detect(payload: Detection, db: Session = Depends(get_db)):
    device = device_for(db, payload.device_id)
    if payload.call_active or call_manager.operators.get(device.device_id):
        return {"ignored": True, "reason": "call_active"}
    incident = await falls.detect(db, device, payload.detection_id, payload.model_dump(exclude={"device_id", "detection_id"}))
    return device_snapshot(db, incident)


@router.get("/{incident_id}", dependencies=[Depends(authenticate)])
async def status(incident_id: str, device_id: str, db: Session = Depends(get_db)):
    incident = incident_for(db, incident_id, device_id)
    await falls.expire(db)
    return device_snapshot(db, incident)


@router.post("/{incident_id}/playback", dependencies=[Depends(authenticate)])
async def playback(incident_id: str, payload: Playback, db: Session = Depends(get_db)):
    incident = incident_for(db, incident_id, payload.device_id)
    await falls.playback(db, incident, payload.ok, payload.remaining_ms)
    return device_snapshot(db, incident)


@router.post("/{incident_id}/audio", dependencies=[Depends(authenticate)])
async def reply(incident_id: str, device_id: str = Form(...), file: UploadFile = File(...),
                playback_finished: bool = Form(False), remaining_ms: int = Form(0, ge=0, le=8000),
                db: Session = Depends(get_db)):
    incident = incident_for(db, incident_id, device_id)
    if incident.state == "waiting_prompt" and playback_finished:
        await falls.playback(db, incident, True, remaining_ms)
    late_started_clip = incident.speech_started and utcnow() < incident.deadline + timedelta(seconds=7)
    if incident.state != "waiting_response" or (utcnow() >= incident.deadline and not late_started_clip):
        return device_snapshot(db, incident)
    incident.stt_until = utcnow() + timedelta(seconds=min(15, settings.stt_timeout_seconds + 2))
    db.commit()
    path = await save_audio(file, device_id)
    try:
        try:
            text = await stt(path, command_only=True)
        except Exception:
            text = ""
    finally:
        path.unlink(missing_ok=True)
    db.refresh(incident)
    if incident.state == "waiting_response":
        incident.stt_until = None
        outcome = falls.classify(text)
        if outcome:
            await falls.finish(db, incident, outcome, "explicit_response", text)
        else:
            falls.history(db.get(Event, incident_id), incident.state, "unrecognized_response", transcript=text)
            db.commit()
            await falls.expire(db)
    return device_snapshot(db, incident)


@router.post("/{incident_id}/speech-start", dependencies=[Depends(authenticate)])
async def speech_start(incident_id: str, payload: Playback, db: Session = Depends(get_db)):
    incident = incident_for(db, incident_id, payload.device_id)
    if incident.state == "waiting_response" and not incident.speech_started and utcnow() < incident.deadline:
        incident.speech_started = True
        incident.stt_until = incident.deadline + timedelta(seconds=7 + min(15, settings.stt_timeout_seconds + 2))
        falls.history(db.get(Event, incident_id),
                      incident.state, "speech_started_within_window")
        db.commit()
    return device_snapshot(db, incident)
