from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services.worker_operations import day_seconds, intervals


def accounts(client):
    suffix = uuid4().hex[:12]
    admin = client.post('/api/auth/register', json={'username': 'ORG' + suffix, 'password': '2468', 'site_name': '배정 현장'}).json()
    admin_headers = {'Authorization': f"Bearer {admin['token']}"}
    worker_id = client.get('/api/dashboard/snapshot', headers=admin_headers).json()['workers'][0]['worker_id']
    invite = client.post(f'/api/auth/worker-invites/{worker_id}', headers=admin_headers).json()['invite_code']
    assert client.post('/api/auth/signup', json={'username': 'EMP' + suffix, 'password': 'secure-password', 'invite_code': invite}).status_code == 200
    worker = client.post('/api/auth/login', json={'username': 'EMP' + suffix, 'password': 'secure-password'}).json()
    return admin_headers, {'Authorization': f"Bearer {worker['token']}"}, worker_id


def test_checklist_and_work_status_are_shared_with_admin():
    with TestClient(app) as client:
        admin, worker, worker_id = accounts(client)
        assert client.post('/api/worker-app/work/start', headers=worker).status_code == 400
        assert client.post('/api/worker-app/work/start', headers=worker, json={'helmet': True, 'vest': True, 'glove': False}).status_code == 400
        for kind, state in [('start', 'working'), ('break_start', 'break'), ('break_end', 'working'), ('end', 'off')]:
            response = client.post(f'/api/worker-app/work/{kind}', headers=worker, json={'helmet': True, 'vest': True, 'glove': True})
            assert response.status_code == 200
            snapshot = client.get('/api/dashboard/snapshot', headers=admin).json()
            target = next(w for w in snapshot['workers'] if w['worker_id'] == worker_id)
            assert target['work']['state'] == state


def test_education_permit_assignment_and_expiry_gate():
    with TestClient(app) as client:
        admin, worker, worker_id = accounts(client)
        path = f'/api/workers/{worker_id}/operations'
        payload = {'organization': '한미르', 'team': 'A팀', 'job_title': '현장반장', 'qualifications': [
            {'kind': 'education', 'name': '현장 안전 교육', 'required': True, 'completed': False},
            {'kind': 'permit', 'name': '화기 작업 허가', 'required': True, 'completed': True, 'expires_on': '2000-01-01'}]}
        assert client.put(path, headers=admin, json=payload).status_code == 200
        me = client.get('/api/worker-app/me', headers=worker).json()
        assert me['worker']['organization'] == '한미르'
        assert me['worker']['job_title'] == '현장반장'
        assert me['eligibility']['can_work'] is False
        assert len(me['eligibility']['reasons']) == 2
        assert client.post('/api/worker-app/work/start', headers=worker, json={'helmet': True, 'vest': True, 'glove': True}).status_code == 409
        payload['qualifications'][0]['completed'] = True
        payload['qualifications'][1]['expires_on'] = '2099-12-31'
        assert client.put(path, headers=admin, json=payload).status_code == 200
        assert client.get('/api/worker-app/me', headers=worker).json()['eligibility']['can_work'] is True
        assert client.put(path, headers=worker, json=payload).status_code == 403
        other_admin, _, _ = accounts(client)
        assert client.get(path, headers=other_admin).status_code == 404


def test_team_chat_is_persistent_and_scoped_by_site_and_team():
    with TestClient(app) as client:
        admin, worker, worker_id = accounts(client)
        other_admin, other_worker, _ = accounts(client)
        assert client.post('/api/worker-app/chat', headers=worker, json={'content': '안전 점검 완료'}).status_code == 200
        assert client.post(f'/api/workers/{worker_id}/chat', headers=admin, json={'content': '확인했습니다'}).status_code == 200
        messages = client.get('/api/worker-app/chat', headers=worker).json()['messages']
        assert [m['content'] for m in messages] == ['안전 점검 완료', '확인했습니다']
        assert client.get('/api/worker-app/chat', headers=other_worker).json()['messages'] == []
        assert client.get(f'/api/workers/{worker_id}/chat', headers=other_admin).status_code == 404
        assert client.post('/api/worker-app/chat', headers=worker, json={'content': '   '}).status_code == 400
        assert client.get('/api/worker-app/chat', headers=worker, params={'before': messages[-1]['message_id']}).json()['messages'][0]['content'] == '안전 점검 완료'
        assert client.put(f'/api/workers/{worker_id}/operations', headers=admin, json={'team': '새 팀', 'job_title': '반장'}).status_code == 200
        assert client.get('/api/worker-app/chat', headers=worker).json()['messages'] == []


def test_calendar_splits_overnight_shift_and_excludes_breaks():
    # KST: Jan 1 23:00 -> Jan 2 01:00, break 00:00 -> 00:30.
    rows = [SimpleNamespace(kind=kind, created_at=datetime.fromisoformat(moment)) for kind, moment in [
        ('start', '2026-01-01T14:00:00'), ('break_start', '2026-01-01T15:00:00'),
        ('break_end', '2026-01-01T15:30:00'), ('end', '2026-01-01T16:00:00')]]
    state, spans = intervals(rows, datetime(2026, 1, 2, tzinfo=timezone.utc))
    assert state == 'off'
    assert day_seconds(spans, date(2026, 1, 1)) == 3600
    assert day_seconds(spans, date(2026, 1, 2)) == 1800
    assert day_seconds(spans, date(2026, 1, 3)) == 0


def test_calendar_map_and_registration_conditions_are_not_public():
    with TestClient(app) as client:
        _, worker, _ = accounts(client)
        calendar = client.get('/api/worker-app/calendar', headers=worker, params={'month': '2026-02'}).json()
        assert len(calendar['days']) == 28
        assert all('records' in day and 'intervals' in day for day in calendar['days'])
        assert client.get('/api/worker-app/calendar', headers=worker, params={'month': 'invalid'}).status_code == 400
        map_data = client.get('/api/worker-app/map', headers=worker).json()
        assert map_data['site']['name'] == '배정 현장'
        assert 'workers' not in map_data
        assert all('allowed_worker_ids' not in zone for zone in map_data['zones'])
        assert client.get('/api/worker-app/map').status_code == 401
