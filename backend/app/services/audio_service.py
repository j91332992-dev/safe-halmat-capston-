from pathlib import Path
import asyncio
import zlib
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from ..config import BASE_DIR
from .whisper_service import transcribe_audio

AUDIO_DIR = BASE_DIR / "audio_data"
AUDIO_DIR.mkdir(exist_ok=True)
_uploaded_bytes = 0
_uploaded_files = 0
_decoded_bytes = 0
_compressed_files = 0

def upload_stats():
    return {'uploaded_bytes':_uploaded_bytes,'uploaded_files':_uploaded_files,
            'decoded_bytes':_decoded_bytes,'compressed_files':_compressed_files}


def decode_audio_transport(data: bytes) -> bytes:
    # Bounded, lossless transport only. VAD/wake/STT always receive original PCM.
    decoder = zlib.decompressobj()
    try:
        decoded = decoder.decompress(data, 2 * 1024 * 1024 + 1)
    except zlib.error as exc:
        raise HTTPException(400, 'Invalid compressed WAV') from exc
    if (len(decoded) > 2 * 1024 * 1024 or not decoder.eof or decoder.unconsumed_tail
            or decoder.unused_data or not decoded.startswith(b'RIFF') or decoded[8:12] != b'WAVE'):
        raise HTTPException(400, 'Invalid or oversized compressed WAV')
    return decoded


async def save_audio(file: UploadFile, device_id: str) -> Path:
    compressed = file.content_type == 'application/x-hanmir-wav-zlib'
    suffix = '.wav' if compressed else Path(file.filename or "audio.wav").suffix or ".wav"
    target = AUDIO_DIR / f"{device_id}_{uuid4().hex}{suffix}"
    data=await file.read()
    global _uploaded_bytes, _uploaded_files, _decoded_bytes, _compressed_files
    _uploaded_bytes+=len(data)
    _uploaded_files+=1
    if compressed:
        data = await asyncio.to_thread(decode_audio_transport, data)
        _compressed_files += 1
    _decoded_bytes += len(data)
    await asyncio.to_thread(target.write_bytes, data)
    return target


async def stt(audio_path: Path, *, command_only: bool = False, confirmation_mode: bool = False) -> str:
    # 실제 STT가 실패하거나 비활성화된 경우 명령을 만들지 않는다.
    # 상시 마이크에서 가짜 테스트 문장은 반복 오작동을 일으킬 수 있다.
    return (await transcribe_audio(audio_path, command_only=command_only, confirmation_mode=confirmation_mode) or "").strip()
