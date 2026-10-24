import asyncio
import json
from secrets import compare_digest
from time import monotonic
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal, get_db
from ..models.entities import Device
from ..services import imu_capture_service as capture
from ..websocket import manager
from .auth import require_site

router=APIRouter(prefix='/api/imu',tags=['imu'])


def _identity(device_id):
    with SessionLocal() as db:
        device=db.get(Device,device_id)
        if not device or device.device_type!='assistant_device':return None
        return device.site_id


@router.websocket('/stream/{device_id}')
async def stream(websocket:WebSocket,device_id:str):
    header=websocket.headers.get('authorization','')
    token=header[7:] if header.startswith('Bearer ') else ''
    if not settings.call_device_token or not token or not compare_digest(settings.call_device_token,token):
        await websocket.close(code=4401);return
    site_id=await asyncio.to_thread(_identity,device_id)
    if not site_id:
        await websocket.close(code=4404);return
    await websocket.accept()
    last_publish=0.
    window=monotonic();messages=0
    try:
        while True:
            text=await websocket.receive_text()
            if len(text)>16384:
                capture.rejected()
                await websocket.close(code=1009);return
            now=monotonic()
            if now-window>=1:window=now;messages=0
            messages+=1
            if messages>50:
                capture.rejected()
                await websocket.close(code=1008);return
            try:
                packet=capture.validate_batch(json.loads(text))
            except (ValueError,TypeError,KeyError):
                capture.rejected()
                await websocket.close(code=1008);return
            state=capture.ingest(device_id,site_id,packet,len(text.encode('utf-8')))
            candidates=state['unique_candidates']
            from ..services import fall_confirmation
            fall_confirmation.submit(device_id,site_id,packet,candidates)
            if candidates:
                # Raw candidate remains diagnostic; confirmation is explicitly enrolled above.
                await manager.broadcast('imu_candidate',dict(device_id=device_id,site_id=site_id,
                    boot=packet['boot'],shadow=True,records=candidates),site_id=site_id)
            if now-last_publish>=.5:
                last_publish=now
                await manager.broadcast('imu_summary',dict(device_id=device_id,site_id=site_id,
                    received_at=state['received_at'],metrics=state['metrics']),site_id=site_id)
    except WebSocketDisconnect:pass


def _device(db,device_id,site_id):
    device=db.get(Device,device_id)
    if not device or device.site_id!=site_id or device.device_type!='assistant_device':
        raise HTTPException(404,'안전모를 찾을 수 없습니다.')
    return device


@router.get('/{device_id}/status')
def status(device_id:str,site_id:str=Depends(require_site),db:Session=Depends(get_db)):
    device=_device(db,device_id,site_id)
    components=json.loads(device.component_status_json or '{}')
    from ..services import fall_confirmation
    return dict(device_id=device_id,mode='shadow',confirmation=fall_confirmation.status(device_id),live=capture.snapshot(device_id),
        heartbeat=components.get('imu_diagnostics'),log=capture.log_status())


class CaptureControl(BaseModel):
    enabled:bool
    duration_s:int=Field(default=600,ge=1,le=1800)


async def _command(db,device_id,site_id,kind,payload):
    device=_device(db,device_id,site_id)
    if not (device.firmware_version or '').startswith('2.0.0-p4-imu-shadow-'):
        raise HTTPException(409,'가속도·각속도 수집 펌웨어를 먼저 적용해야 합니다.')
    delivered=await manager.send_device_command(device_id,dict(command_id=str(uuid4()),
        command_type=kind,payload=payload))
    if not delivered:raise HTTPException(409,'안전모 명령 채널이 오프라인입니다.')
    return dict(delivered=True,applied=False,
                note='전달됨. 실제 적용·센서 수신·기준 설정 완료 여부는 status로 확인하세요.')


@router.post('/{device_id}/capture')
async def control(device_id:str,payload:CaptureControl,site_id:str=Depends(require_site),db:Session=Depends(get_db)):
    return await _command(db,device_id,site_id,'set_imu_capture',payload.model_dump())


@router.post('/{device_id}/baseline')
async def baseline(device_id:str,site_id:str=Depends(require_site),db:Session=Depends(get_db)):
    # Operator must first place the worn helmet upright; IMU cannot prove wearing.
    return await _command(db,device_id,site_id,'imu_set_baseline',{})


class FallControl(BaseModel):
    enabled:bool


@router.post('/{device_id}/fall-monitoring')
async def fall_monitoring(device_id:str,payload:FallControl,site_id:str=Depends(require_site),db:Session=Depends(get_db)):
    _device(db,device_id,site_id)
    from ..services import fall_confirmation
    live=capture.snapshot(device_id) or {};metrics=live.get('metrics',{})
    if payload.enabled:
        if live.get('age_ms',99999)>1500 or not metrics.get('baseline_ready') or metrics.get('calibration_pending'):
            raise HTTPException(409,'최신 유효 센서 수신과 정상 착용 자세 기준 저장이 필요합니다.')
        if any(metrics.get(k,{}).get('accuracy',0)<1 for k in ('accel','gyro','fall_rotation')):
            raise HTTPException(409,'센서 신뢰 상태가 부족합니다. 보정 후 다시 활성화하세요.')
    # Keep the endpoint session idle while the worker thread commits independently.
    return await asyncio.to_thread(fall_confirmation.configure,device_id,site_id,payload.enabled,
                                  live.get('boot'),metrics.get('baseline_generation'))
