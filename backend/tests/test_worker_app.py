from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app


def test_worker_session_is_scoped_and_sos_reaches_dashboard():
    with TestClient(app) as client:
        login = client.post('/api/auth/login', json={'username': 'worker', 'password': '0000'})
        assert login.status_code == 200
        session = login.json()
        assert session['role'] == 'worker'
        headers = {'Authorization': f"Bearer {session['token']}"}
        me = client.get('/api/worker-app/me', headers=headers)
        assert me.status_code == 200
        assert me.json()['worker']['worker_id'] == session['worker_id']
        assert client.get('/api/dashboard/snapshot', headers=headers).status_code == 403
        assert client.post('/api/auth/register', json={'username': 'WORKER', 'password': '1234'}).status_code == 409
        with patch('app.routers.worker_app.manager.broadcast', new_callable=AsyncMock) as broadcast:
            response = client.post('/api/worker-app/sos', headers=headers)
            assert response.status_code == 200
            assert response.json()['worker_id'] == session['worker_id']
            assert response.json()['site_id'] == session['site_id']
            assert broadcast.await_count == 1
            assert broadcast.await_args.kwargs['site_id'] == session['site_id']
        assert client.get('/api/worker-app/me', headers=headers).json()['worker']['emergency'] is True
        assert response.json()['details']['intent'] == 'emergency'
        assert client.post('/api/worker-app/sos', headers=headers).json()['event_id'] == response.json()['event_id']
        admin = client.post('/api/auth/login', json={'username': 'TUTUS', 'password': '0000'}).json()
        admin_headers = {'Authorization': f"Bearer {admin['token']}"}
        assert client.post(f"/api/events/{response.json()['event_id']}/acknowledge", headers=admin_headers).status_code == 200
        assert client.get('/api/worker-app/me', headers=headers).json()['worker']['emergency'] is True
        assert client.post(f"/api/events/{response.json()['event_id']}/resolve", headers=admin_headers).status_code == 200
        assert client.get('/api/worker-app/me', headers=headers).json()['worker']['emergency'] is False


def test_worker_call_reuses_manager_call_flow():
    with TestClient(app) as client:
        session = client.post('/api/auth/login', json={'username': 'WORKER', 'password': '0000'}).json()
        headers = {'Authorization': f"Bearer {session['token']}"}
        assert client.post('/api/worker-app/call-manager').status_code == 401
        with patch('app.routers.worker_app.call_manager.device_online', return_value=False):
            assert client.post('/api/worker-app/call-manager', headers=headers).status_code == 409
        with patch('app.routers.worker_app.call_manager.device_online', return_value=True), patch('app.routers.worker_app.call_manager.begin_call_request', new_callable=AsyncMock) as begin:
            response = client.post('/api/worker-app/call-manager', headers=headers)
            assert response.status_code == 200
            row = response.json()
            assert row['details']['intent'] == 'call_manager'
            begin.assert_awaited_once_with(row['device_id'], session['worker_id'], row['event_id'])
            assert client.post('/api/worker-app/call-manager', headers=headers).json()['event_id'] == row['event_id']
            assert begin.await_count == 1


def test_worker_work_transitions_reject_duplicate_start():
    with TestClient(app) as client:
        session = client.post('/api/auth/login', json={'username': 'WORKER', 'password': '0000'}).json()
        headers = {'Authorization': f"Bearer {session['token']}"}
        for kind in ('start', 'break_start', 'break_end', 'end'):
            assert client.post(f'/api/worker-app/work/{kind}', headers=headers, json={"helmet": True, "vest": True, "glove": True}).status_code == 200
            assert client.post(f'/api/worker-app/work/{kind}', headers=headers).status_code == 409
        assert client.get('/api/worker-app/me', headers=headers).json()['work']['state'] == 'off'
