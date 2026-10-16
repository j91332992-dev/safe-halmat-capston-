from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from ..config import BASE_DIR
from .whisper_service import transcribe_audio

AUDIO_DIR = BASE_DIR / "audio_data"
AUDIO_DIR.mkdir(exist_ok=True)
_uploaded_bytes = 0
_uploaded_files = 0

def upload_stats():
    return {'uploaded_bytes':_uploaded_bytes,'uploaded_files':_uploaded_files}


async def save_audio(file: UploadFile, device_id: str) -> Path:
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    target = AUDIO_DIR / f"{device_id}_{uuid4().hex}{suffix}"
    data=await file.read()
    global _uploaded_bytes, _uploaded_files
    _uploaded_bytes+=len(data)
    _uploaded_files+=1
    target.write_bytes(data)
    return target


async def stt(audio_path: Path, *, command_only: bool = False) -> str:
    # 실제 STT가 실패하거나 비활성화된 경우 명령을 만들지 않는다.
    # 상시 마이크에서 가짜 테스트 문장은 반복 오작동을 일으킬 수 있다.
    return (await transcribe_audio(audio_path, command_only=command_only) or "").strip()
