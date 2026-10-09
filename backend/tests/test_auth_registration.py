from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.websocket import manager


def test_registration_creates_an_isolated_site_and_logs_in():
    with TestClient(app) as client:
        registered = client.post(
            "/api/auth/register",
            json={"username": "NEWCOMPANY", "password": "2468", "site_name": "신규 회사 테스트 현장"},
        )
        assert registered.status_code == 201
        body = registered.json()
        assert body["username"] == "NEWCOMPANY"
        assert body["site_id"].startswith("site-")

        headers = {"Authorization": f"Bearer {body['token']}"}
        snapshot = client.get("/api/dashboard/snapshot", headers=headers)
        assert snapshot.status_code == 200
        data = snapshot.json()
        assert data["site"]["name"] == "신규 회사 테스트 현장"
        assert data["workers"]
        assert all(worker["worker_id"].startswith(body["site_id"]) for worker in data["workers"])
        assert all(device["site_id"] == body["site_id"] for device in data["devices"])

        login = client.post("/api/auth/login", json={"username": "newcompany", "password": "2468"})
        assert login.status_code == 200
        assert login.json()["site_id"] == body["site_id"]


def test_duplicate_username_is_rejected_case_insensitively():
    with TestClient(app) as client:
        availability = client.get("/api/auth/username-available", params={"username": "tutus"})
        assert availability.status_code == 200
        assert availability.json()["available"] is False

        duplicate = client.post(
            "/api/auth/register",
            json={"username": "tutus", "password": "9999", "site_name": "중복 현장"},
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"] == "이미 사용 중인 아이디입니다."


def test_registration_without_company_name_creates_a_default_site_name():
    with TestClient(app) as client:
        registered = client.post(
            "/api/auth/register",
            json={"username": "NOORGCOMPANY", "password": "2468"},
        )
        assert registered.status_code == 201
        body = registered.json()
        headers = {"Authorization": f"Bearer {body['token']}"}
        snapshot = client.get("/api/dashboard/snapshot", headers=headers)
        assert snapshot.status_code == 200
        assert snapshot.json()["site"]["name"] == "NOORGCOMPANY 현장"


def test_accounts_cannot_read_or_modify_another_company_site():
    with TestClient(app) as client:
        company_a = client.post(
            "/api/auth/register",
            json={"username": "ISOLATEDA", "password": "2468", "site_name": "A 회사"},
        ).json()
        company_b = client.post(
            "/api/auth/register",
            json={"username": "ISOLATEDB", "password": "2468", "site_name": "B 회사"},
        ).json()
        headers_a = {"Authorization": f"Bearer {company_a['token']}"}
        headers_b = {"Authorization": f"Bearer {company_b['token']}"}

        snapshot_a = client.get("/api/dashboard/snapshot", headers=headers_a).json()
        snapshot_b = client.get("/api/dashboard/snapshot", headers=headers_b).json()
        assert snapshot_a["site"]["name"] == "A 회사"
        assert snapshot_b["site"]["name"] == "B 회사"
        assert {item["worker_id"] for item in snapshot_a["workers"]}.isdisjoint(
            {item["worker_id"] for item in snapshot_b["workers"]}
        )

        a_worker_id = snapshot_a["workers"][0]["worker_id"]
        denied = client.put(
            f"/api/workers/{a_worker_id}",
            headers=headers_b,
            json={"worker_name": "침범 시도", "worker_role": "general_worker", "notes": ""},
        )
        assert denied.status_code == 404
        anchors_b = client.get("/api/anchors", headers=headers_b).json()
        assert anchors_b
        assert all(item["anchor_id"].startswith(company_b["site_id"]) for item in anchors_b)


def test_dashboard_websocket_requires_login_and_is_bound_to_the_session_site():
    with TestClient(app) as client:
        try:
            with client.websocket_connect("/ws/dashboard"):
                raise AssertionError("인증 없는 대시보드 연결이 허용되었습니다.")
        except WebSocketDisconnect as exc:
            assert exc.code == 4401

        registered = client.post(
            "/api/auth/register",
            json={"username": "WSISOLATION", "password": "2468", "site_name": "웹소켓 분리 현장"},
        ).json()
        site_id = registered["site_id"]
        before = len(manager.dashboard.get(site_id, []))
        with client.websocket_connect(f"/ws/dashboard?token={registered['token']}"):
            assert len(manager.dashboard.get(site_id, [])) == before + 1
        assert len(manager.dashboard.get(site_id, [])) == before
