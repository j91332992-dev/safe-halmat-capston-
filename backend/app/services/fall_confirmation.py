"""Bounded fall confirmation; sensor candidates never assert a confirmed injury."""
import asyncio
import json
from datetime import datetime, timezone
from time import monotonic
from uuid import uuid4

from ..database import SessionLocal
from ..models.entities import Device, Event, WorkerState
from ..websocket import manager, call_manager
from .event_service import create_event, event_to_dict
from .speech_service import normalize
from .tts_generator_service import generate_tts
from .voice_trace import record_voice

QUESTION='넘어지셨나요? 괜찮으면 괜찮아, 도움이 필요하면 도와줘라고 말씀해 주세요.'
CANCEL_ACK='알겠습니다. 낙상 알림을 취소했습니다.'
RESPONSE_SECONDS=20
_armed={}
_pending={}
_tasks={}
_cooldown={}


def status(device_id):
    state=_pending.get(device_id)
    return dict(enabled=device_id in _armed, enrollment=_armed.get(device_id),
                pending={k:v for k,v in state.items() if k not in ('ack',)} if state else None,
                response_seconds=RESPONSE_SECONDS)


def configure(device_id,site_id,enabled,boot=None,generation=None):
    enrollment=dict(boot=boot,generation=generation) if enabled else None
    with SessionLocal() as db:
        create_event(db,'FALL_MONITORING','낙상 확인 안내 '+('활성화' if enabled else '중지'),
            device_id=device_id,site_id=site_id,details=dict(enabled=enabled,enrollment=enrollment)).status='resolved'
        db.commit()
    if enabled:_armed[device_id]=enrollment
    else:
        _armed.pop(device_id,None)
        if device_id in _pending:
            _pending[device_id]['cancelled']=True
            _pending[device_id]['ack'].set()
    return status(device_id)


async def restore():
    def load():
        with SessionLocal() as db:
            rows=db.query(Event).filter(Event.event_type=='FALL_MONITORING').order_by(Event.created_at).all()
            for row in rows:
                data=json.loads(row.details_json)
                if data.get('enabled'):_armed[row.device_id]=data['enrollment']
                else:_armed.pop(row.device_id,None)
            interrupted=db.query(Event).filter(Event.event_type=='FALL_CONFIRMATION',Event.status.in_(['pending','acknowledged'])).all()
            result=[]
            for event in interrupted:
                details=json.loads(event.details_json)
                if details.get('outcome')!='awaiting_question':continue
                details['outcome']='server_restarted_before_confirmation'
                event.details_json=json.dumps(details,ensure_ascii=False)
                event.status='open';event.severity='emergency';event.message='낙상 의심 확인 중 서버가 재시작됐습니다. 작업자 상태를 확인하세요.'
                result.append(event_to_dict(event))
            db.commit();return result
    for event in await asyncio.to_thread(load):await manager.broadcast('event',event,site_id=event['site_id'])
    # Cache the fixed question before enabling a real session.
    await generate_tts(QUESTION)
    await generate_tts(CANCEL_ACK)


def submit(device_id,site_id,packet,candidates):
    enrollment=_armed.get(device_id);metrics=packet.get('metrics',{})
    if not enrollment or not candidates or device_id in _tasks or len(_tasks)>=64:return
    if enrollment['boot']!=packet['boot'] or enrollment['generation']!=metrics.get('baseline_generation'):return
    if not metrics.get('baseline_ready') or metrics.get('calibration_pending'):return
    if any(metrics.get(k,{}).get('accuracy',0)<1 or not 0<=metrics.get(k,{}).get('age_ms',9999)<250 for k in ('accel','gyro','fall_rotation')):return
    if monotonic()<_cooldown.get(device_id,0):return
    # An old queued event must not ask the worker about a long-past posture.
    candidate=next((r for r in candidates if 0<=packet['tx_us']-r[4]<=2_000_000),None)
    if candidate is None:return
    task=asyncio.create_task(_session(device_id,site_id,packet,candidate))
    _tasks[device_id]=task


def _new_event(device_id,site_id,evidence):
    with SessionLocal() as db:
        device=db.get(Device,device_id)
        worker=db.get(WorkerState,device.worker_id) if device and device.worker_id else None
        details=dict(evidence=evidence,outcome='awaiting_question',response_seconds=RESPONSE_SECONDS,
            location=dict(x=worker.x,y=worker.y,confidence=worker.confidence,
                measured_at=worker.last_valid_location_at.isoformat() if worker.last_valid_location_at else None) if worker else None)
        event=create_event(db,'FALL_CONFIRMATION','낙상 의심: 작업자 응답 확인 중','warning',
            device.worker_id if device else None,device_id,details,site_id)
        event.status='pending';db.commit();return event_to_dict(event)


def _finish(event_id,outcome,reply=None):
    with SessionLocal() as db:
        event=db.get(Event,event_id)
        if not event or event.status not in ('pending','acknowledged'):return None
        details=json.loads(event.details_json);details.update(outcome=outcome,reply=reply,
            completed_at=datetime.now(timezone.utc).isoformat())
        event.details_json=json.dumps(details,ensure_ascii=False)
        event.status='resolved' if outcome in ('worker_ok','monitor_disabled') else 'open'
        event.severity='info' if event.status=='resolved' else 'emergency'
        labels={'worker_ok':'작업자가 괜찮다고 응답했습니다.',
            'help_requested':'낙상 의심 작업자가 도움을 요청했습니다.',
            'no_response':'낙상 의심 후 작업자 응답이 없습니다. 즉시 상태를 확인하세요.',
            'question_not_confirmed':'낙상 의심: 확인 안내 재생을 확인하지 못했습니다. 작업자 상태를 확인하세요.',
            'call_active':'낙상 의심: 통화 중이므로 관리자가 작업자 상태를 확인하세요.',
            'monitor_disabled':'낙상 확인 안내가 관리자에 의해 중지됐습니다.'}
        event.message=labels.get(outcome,'낙상 확인 처리 오류: 작업자 상태를 확인하세요.')
        db.commit();return event_to_dict(event)


async def _session(device_id,site_id,packet,candidate):
    state=None
    try:
        event=await asyncio.to_thread(_new_event,device_id,site_id,dict(boot=packet['boot'],record=candidate,metrics=packet['metrics']))
        state=dict(event_id=event['event_id'],phase='preparing',ack=asyncio.Event(),command_id=str(uuid4()),reply=None,cancelled=False)
        _pending[device_id]=state
        await manager.broadcast('event',event,site_id=site_id)
        outcome='question_not_confirmed'
        if call_manager.operators.get(device_id) or packet['metrics'].get('call_active'):outcome='call_active'
        else:
            audio=await asyncio.wait_for(generate_tts(QUESTION),timeout=10)
            if audio and not state['cancelled']:
                state['phase']='playing'
                delivered=await asyncio.wait_for(manager.send_device_command(device_id,dict(
                    command_id=state['command_id'],command_type='play_audio',
                    payload=dict(message=QUESTION,audio_url='/tts/'+audio.name,audio_scope='fall_confirmation'))),timeout=2)
                if delivered:
                    try:await asyncio.wait_for(state['ack'].wait(),timeout=30)
                    except asyncio.TimeoutError:pass
                    if state.get('playback_ok'):
                        state['phase']='awaiting_reply';state['deadline']=monotonic()+RESPONSE_SECONDS
                        record_voice('fall_question_played',event['event_id'],device_id=device_id,response_seconds=RESPONSE_SECONDS)
                        while monotonic()<state['deadline'] and not state['reply'] and not state['cancelled']:
                            await asyncio.sleep(.1)
                        outcome=state['reply'] or 'no_response'
        if state['cancelled']:outcome='monitor_disabled'
        finished=await asyncio.to_thread(_finish,event['event_id'],outcome,state.get('transcript'))
        if finished:await manager.broadcast('event',finished,site_id=site_id)
        if outcome=='worker_ok':
            audio=await asyncio.wait_for(generate_tts(CANCEL_ACK),timeout=10)
            if audio:
                delivered=await asyncio.wait_for(manager.send_device_command(device_id,dict(
                    command_id=str(uuid4()),command_type='play_audio',
                    payload=dict(message=CANCEL_ACK,audio_url='/tts/'+audio.name))),timeout=2)
                record_voice('fall_cancel_ack',event['event_id'],device_id=device_id,delivered=bool(delivered))
        record_voice('fall_confirmation',event['event_id'],device_id=device_id,outcome=outcome)
    except asyncio.CancelledError:raise
    except Exception as exc:
        record_voice('fall_confirmation_error',device_id,error=type(exc).__name__)
        if state:
            finished=await asyncio.to_thread(_finish,state['event_id'],'processing_error')
            if finished:await manager.broadcast('event',finished,site_id=site_id)
    finally:
        _pending.pop(device_id,None);_tasks.pop(device_id,None)
        _cooldown[device_id]=monotonic()+120


def speaker_result(device_id,command_id,ok):
    state=_pending.get(device_id)
    if state and state['command_id']==command_id and state['phase']=='playing':
        state['playback_ok']=ok;state['ack'].set()


def resolve_pending(event_id):
    for state in _pending.values():
        if state['event_id']==event_id:
            state['cancelled']=True
            state['ack'].set()


def accept_reply(device_id,text):
    state=_pending.get(device_id)
    if not state or state['phase']!='awaiting_reply' or state['reply'] or monotonic()>state['deadline']:return None
    value=normalize(text)
    if value.startswith('투투스'):value=value[3:]
    help_words=('도와줘','도와주세요','살려줘','살려주세요','안괜찮아','괜찮지않아','괜찮지않아요','도움이필요해요')
    ok_words=('괜찮아','괜찮아요','괜찮습니다','저는괜찮아요','나괜찮아','문제없어','문제없어요','잘못감지했어')
    reply='help_requested' if value in help_words else 'worker_ok' if value in ok_words else None
    if reply:
        state['reply']=reply;state['transcript']=text
        record_voice('fall_reply',state['event_id'],device_id=device_id,outcome=reply)
        return dict(status='fall_reply',intent=reply,response='',timings_ms={},delivered_connections=0)
    return None


def awaiting_reply(device_id):
    state=_pending.get(device_id)
    return bool(state and state['phase']=='awaiting_reply' and not state['reply'] and monotonic()<=state['deadline'])


async def shutdown():
    tasks=list(_tasks.values())
    for task in tasks:task.cancel()
    await asyncio.gather(*tasks,return_exceptions=True)
