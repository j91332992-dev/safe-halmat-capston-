"""30-second zone notices and bounded, acknowledged helmet delivery.

Membership is evaluated in the ordered UWB transaction. Delivery runs separately
and revalidates permission, geometry and location freshness before every attempt.
"""
import asyncio
import json
import wave
from collections import Counter
from datetime import datetime
from time import monotonic, perf_counter
from uuid import uuid4

from ..database import SessionLocal
from ..models.entities import Device, Event, WorkerState, Zone
from ..websocket import manager, call_manager
from .event_service import create_event, event_to_dict
from .zone_service import point_in_zone
from .tts_generator_service import generate_tts
from .voice_trace import record_voice

INTERVAL = 30
_membership = {}  # accessed only by the ordered UWB worker
_pending = {}     # accessed only on the asyncio loop
_stats = Counter()
_tts_slots = asyncio.Semaphore(2)
_voice_last = {}


def evaluate(db, worker):
    now = monotonic()
    events = []
    active = []
    zones = db.query(Zone).filter(Zone.site_id == worker.site_id, Zone.active.is_(True),
        Zone.zone_category.in_(['danger', 'controlled', 'confined'])).all()
    valid = {(worker.site_id, worker.worker_id, z.zone_id) for z in zones}
    for key in list(_membership):
        if key[:2] == (worker.site_id, worker.worker_id) and key not in valid:
            del _membership[key]
    for zone in zones:
        key = (worker.site_id, worker.worker_id, zone.zone_id)
        state = _membership.get(key)
        if state is None:
            if len(_membership) >= 4096:
                _membership.pop(next(iter(_membership)))
            # Preserve the notification throttle across server restarts.
            prior = db.query(Event).filter(Event.site_id == worker.site_id,
                Event.worker_id == worker.worker_id,
                Event.event_type.in_(['DANGER_ZONE_ENTERED', 'DANGER_ZONE_REMINDER']))\
                .order_by(Event.created_at.desc()).limit(100).all()
            age = INTERVAL
            for event in prior:
                if json.loads(event.details_json).get('zone_id') == zone.zone_id:
                    age = max(0, (datetime.utcnow() - event.created_at).total_seconds())
                    break
            state = _membership[key] = dict(inside=False, count=0, last=now-min(age, INTERVAL))
        unauthorized = worker.worker_id not in json.loads(zone.allowed_worker_ids_json)
        inside = unauthorized and point_in_zone(worker.x, worker.y, zone)
        state['count'] = min(3, max(0,state['count'])+1) if inside else max(-3, min(0,state['count'])-1)
        entered = not state['inside'] and state['count'] >= 3
        exited = state['inside'] and (not unauthorized or state['count'] <= -3)
        if entered: state['inside'] = True
        if exited:
            state['inside'] = False
            events.append(event_to_dict(create_event(db, 'ZONE_EXITED',
                f'{zone.zone_name} 경고를 해제했습니다.', 'info', worker.worker_id,
                details=dict(zone_id=zone.zone_id), site_id=worker.site_id)))
        if not state['inside']: continue
        active.append(zone.zone_id)
        if now-state['last'] < INTERVAL: continue
        state['last'] = now
        message = (zone.warning_message or f'{zone.zone_name}에 진입했습니다.')[:160]
        message += ' 허가되지 않은 구역입니다. 구역 밖으로 이동하세요.'
        event = create_event(db, 'DANGER_ZONE_ENTERED' if entered else 'DANGER_ZONE_REMINDER',
            message, 'danger', worker.worker_id, details=dict(zone_id=zone.zone_id,
                interval_seconds=INTERVAL, delivery='pending'), site_id=worker.site_id)
        events.append(event_to_dict(event))
    worker.current_zone = active[0] if active else None
    return events


def _eligible(job):
    with SessionLocal() as db:
        worker = db.get(WorkerState, job['worker_id'])
        zone = db.get(Zone, job['zone_id'])
        if not worker or not zone or worker.site_id != job['site_id'] or zone.site_id != worker.site_id:
            return None
        if not zone.active or zone.zone_category not in ('danger','controlled','confined'):
            return None
        if worker.worker_id in json.loads(zone.allowed_worker_ids_json): return None
        if not worker.last_valid_location_at or (datetime.utcnow()-worker.last_valid_location_at).total_seconds() > 2:
            return None
        if not point_in_zone(worker.x, worker.y, zone): return None
        device = db.query(Device).filter(Device.site_id == worker.site_id,
            Device.worker_id == worker.worker_id, Device.device_type == 'assistant_device')\
            .order_by(Device.last_seen.desc()).first()
        return device.device_id if device else ''


def submit(events):
    for event in events:
        _stats['web_events'] += 1
        record_voice('zone_warning_web',event['event_id'],site_id=event['site_id'],
            worker_id=event['worker_id'],event_type=event['event_type'])
        if event['event_type'] not in ('DANGER_ZONE_ENTERED','DANGER_ZONE_REMINDER'): continue
        key = (event['site_id'],event['worker_id'],event['details']['zone_id'])
        if key in _pending:
            # While a call is active keep a single latest notice, never a backlog.
            _stats['coalesced'] += 1
            continue
        if len(_pending) >= 128:
            _stats['capacity_rejected'] += 1
            record_voice('zone_warning_capacity',event['event_id'])
            continue
        job = dict(site_id=key[0],worker_id=key[1],zone_id=key[2],event_id=event['event_id'],
            message=event['message'],command_id=str(uuid4()),ack=asyncio.Event(),attempts=0)
        _pending[key] = job
        job['task'] = asyncio.create_task(_deliver(key,job))


def speaker_result(device_id,command_id,ok):
    for job in _pending.values():
        if job.get('device_id') == device_id and job['command_id'] == command_id:
            job['ok'] = bool(ok); job['ack'].set()


def _save_result(job,outcome):
    with SessionLocal() as db:
        event = db.get(Event,job['event_id'])
        if event:
            data = json.loads(event.details_json)
            data.update(delivery=outcome,attempts=job['attempts'],command_id=job['command_id'])
            event.details_json = json.dumps(data,ensure_ascii=False)
            db.commit()


async def _deliver(key,job):
    outcome = 'expired'
    started = perf_counter()
    try:
        audio = None
        deferred = False
        deadline = monotonic()+25
        while True:
            device_id = await asyncio.to_thread(_eligible,job)
            if device_id is None:
                outcome = 'left_or_stale_or_allowed'; break
            job['device_id'] = device_id
            if device_id and call_manager.operators.get(device_id):
                if not deferred:
                    _stats['call_deferred'] += 1
                    record_voice('zone_warning_deferred',job['event_id'],device_id=device_id)
                deferred = True
                # Call time does not consume the retry window. Geometry is
                # checked every second, so leaving cancels the deferred notice.
                deadline = monotonic()+25
                await asyncio.sleep(1); continue
            if monotonic() >= deadline or job['attempts'] >= 3: break
            if not device_id:
                await asyncio.sleep(1); continue
            if monotonic()-_voice_last.get(key,-INTERVAL) < INTERVAL:
                deadline = monotonic()+25
                await asyncio.sleep(1); continue
            if audio is None:
                async with _tts_slots:
                    audio = await asyncio.wait_for(generate_tts(job['message']),10)
                if not audio: outcome = 'tts_failed'; break
                with wave.open(str(audio),'rb') as wav:
                    job['ack_timeout'] = min(20, wav.getnframes()/wav.getframerate()+4)
                continue  # recheck call and location after TTS preparation
            job['attempts'] += 1
            job['last_send_at'] = monotonic()
            job['ack'].clear(); job['ok'] = False
            try:
                sent = await asyncio.wait_for(manager.send_device_command(device_id,dict(
                command_id=job['command_id'],command_type='play_audio',payload=dict(
                    message=job['message'],audio_url='/tts/'+audio.name,
                    audio_scope='zone_warning',valid_for_ms=5000))),2)
            except (asyncio.TimeoutError, ConnectionError):
                sent = 0
                _stats['send_timeout_or_disconnect'] += 1
            _stats['attempts'] += 1
            record_voice('zone_warning_attempt',job['event_id'],device_id=device_id,
                attempt=job['attempts'],delivered=sent)
            if sent:
                try: await asyncio.wait_for(job['ack'].wait(),job['ack_timeout'])
                except asyncio.TimeoutError: pass
                if job['ok']:
                    _voice_last[key] = job['last_send_at']
                    if len(_voice_last) > 4096: _voice_last.pop(next(iter(_voice_last)))
                    outcome = 'played'; break
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        outcome = 'server_stopped'; raise
    except Exception as exc:
        outcome = 'delivery_error'
        record_voice('zone_warning_error',job['event_id'],error=type(exc).__name__)
    finally:
        _stats[outcome] += 1
        record_voice('zone_warning_result',job['event_id'],outcome=outcome,
            attempts=job['attempts'],elapsed_ms=round((perf_counter()-started)*1000,1))
        await asyncio.to_thread(_save_result,job,outcome)
        _pending.pop(key,None)


def status(site_id):
    return dict(interval_seconds=INTERVAL,pending=[dict(worker_id=j['worker_id'],
        zone_id=j['zone_id'],attempts=j['attempts']) for j in _pending.values()
        if j['site_id']==site_id], counters=dict(_stats))


async def shutdown():
    tasks = [j['task'] for j in list(_pending.values())]
    for task in tasks: task.cancel()
    await asyncio.gather(*tasks,return_exceptions=True)
