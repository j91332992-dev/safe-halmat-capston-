from fastapi.testclient import TestClient

from app.main import app
from app.websocket import call_manager


def test_remote_administrator_can_call_only_assigned_site(monkeypatch):
    monkeypatch.setattr(call_manager, "device_online", lambda device_id: True)
    with TestClient(app, client=("192.168.0.22", 53000)) as client:
        admin = client.post('/api/auth/login', json={'username': 'TUTUS', 'password': '0000'}).json()
        headers = {'Authorization': f"Bearer {admin['token']}"}
        site_b = client.post('/api/auth/login', json={'username': 'TUTUS2', 'password': '0000'}).json()
        other_headers = {'Authorization': f"Bearer {site_b['token']}"}
        path = '/api/calls/helmet-001-av/ticket'
        assert client.post(path).status_code == 401
        assert client.post(path, headers=other_headers).status_code == 404
        response = client.post(path, headers=headers)
        assert response.status_code == 200
        assert response.json()['expires_in'] == 30
        worker = client.post('/api/auth/login', json={'username': 'WORKER', 'password': '0000'}).json()
        assert client.post(path, headers={'Authorization': f"Bearer {worker['token']}"}).status_code == 403
