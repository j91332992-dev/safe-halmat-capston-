from fastapi.testclient import TestClient

from app.main import app


def login_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": "TUTUS", "password": "0000"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_layout_and_obstacle_round_trip():
    obstacle_id = "test-obstacle-round-trip"
    with TestClient(app) as client:
        headers = login_headers(client)
        layout = client.get("/api/layout", headers=headers)
        assert layout.status_code == 200
        assert layout.json()["site"]["width"] > 0

        client.delete(f"/api/layout/obstacles/{obstacle_id}", headers=headers)
        payload = {
            "obstacle_id": obstacle_id,
            "name": "테스트 장애물",
            "x": 1.0,
            "y": 1.5,
            "width": 0.8,
            "height": 1.2,
        }
        created = client.post("/api/layout/obstacles", json=payload, headers=headers)
        assert created.status_code == 200
        assert created.json()["name"] == "테스트 장애물"

        payload["x"] = 2.0
        updated = client.put(f"/api/layout/obstacles/{obstacle_id}", json=payload, headers=headers)
        assert updated.status_code == 200
        assert updated.json()["x"] == 2.0

        snapshot = client.get("/api/dashboard/snapshot", headers=headers).json()
        assert any(item["obstacle_id"] == obstacle_id for item in snapshot["obstacles"])

        deleted = client.delete(f"/api/layout/obstacles/{obstacle_id}", headers=headers)
        assert deleted.status_code == 204
