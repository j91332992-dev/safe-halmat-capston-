"""Administrator-only PPE events. Never enqueue a device/audio command."""
import json
from uuid import uuid4

from ..database import SessionLocal, utcnow
from ..models.entities import Device, Event
from .event_service import event_to_dict
from .camera_service import CAPTURE_DIR

LABELS = {'helmet': '안전모', 'vest': '조끼', 'glove': '장갑'}


def persist_ppe_notifications(notes, jpeg=None):
    results = []
    photo = None
    if jpeg and any(n['kind'] in {'opened', 'reminder'} for n in notes):
        photo = f'ppe_{uuid4().hex}.jpg'
        (CAPTURE_DIR/photo).write_bytes(jpeg)
    with SessionLocal() as db:
        for note in notes:
            device = db.query(Device).filter(Device.device_id == note['device']).first()
            if not device:
                continue
            key = f"ppe-{note['track_id']}-{note['item']}"
            event = db.get(Event, key)
            kind = note['kind']
            label = LABELS[note['item']]
            state = ('착용 확인 필요' if note['item'] == 'glove' else '미착용 의심')
            if kind == 'resolved':
                state = '착용 재확인 · 해소'
            elif kind == 'observation_ended':
                state = '관측 종료 · 착용 여부 확인 불가'
            message = f"전방 사람 {note['track_id'].split('-')[-1]} · {label} {state}"
            details = dict(note, subject_scope='observed_person', audience='administrator',
                           notify=kind in {'opened', 'reminder'}, updated_at=utcnow().isoformat()+'Z')
            if photo:
                details['url'] = f'/captures/{photo}'
            if event is None:
                if kind not in {'opened', 'reminder'}:
                    continue
                event = Event(event_id=key, site_id=device.site_id, event_type='PPE_OBSERVATION',
                    severity='warning', worker_id=device.worker_id, device_id=device.device_id,
                    message=message, details_json=json.dumps(details, ensure_ascii=False))
                db.add(event)
            else:
                old_details = json.loads(event.details_json or '{}')
                if not details.get('person'):
                    details['person'] = old_details.get('person')
                if not details.get('url') and old_details.get('url'):
                    details['url'] = old_details['url']
                event.message = message
                event.details_json = json.dumps(details, ensure_ascii=False)
            event.status = 'resolved' if kind in {'resolved', 'observation_ended'} else 'open'
            event.severity = 'info' if event.status == 'resolved' else 'warning'
            db.flush()
            results.append(event_to_dict(event))
        db.commit()
    return results


def close_previous_ppe_observations():
    # Tracking IDs are scoped to a server session; restart is not PPE recovery.
    with SessionLocal() as db:
        rows = db.query(Event).filter(Event.event_type == 'PPE_OBSERVATION', Event.status != 'resolved').all()
        for event in rows:
            details = json.loads(event.details_json or '{}')
            details.update(kind='observation_ended', notify=False, reason='server_restart')
            event.status = 'resolved'
            event.severity = 'info'
            event.message = '서버 재시작 · 보호구 관측 종료 · 착용 여부 확인 불가'
            event.details_json = json.dumps(details, ensure_ascii=False)
        db.commit()
