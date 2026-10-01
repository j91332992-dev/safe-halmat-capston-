from fastapi.testclient import TestClient

from app.main import app


def test_layout_and_obstacle_round_trip():
    obstacle_id = "test-obstacle-round-trip"
    with TestClient(app) as client:
        layout = client.get("/api/layout")
        assert layout.status_code == 200
        assert layout.json()["site"]["width"] > 0

        client.delete(f"/api/layout/obstacles/{obstacle_id}")
        payload = {
            "obstacle_id": obstacle_id,
            "name": "테스트 장애물",
            "x": 1.0,
            "y": 1.5,
            "width": 0.8,
            "height": 1.2,
        }
        created = client.post("/api/layout/obstacles", json=payload)
        assert created.status_code == 200
        assert created.json()["name"] == "테스트 장애물"

        payload["x"] = 2.0
        updated = client.put(f"/api/layout/obstacles/{obstacle_id}", json=payload)
        assert updated.status_code == 200
        assert updated.json()["x"] == 2.0

        snapshot = client.get("/api/dashboard/snapshot").json()
        assert any(item["obstacle_id"] == obstacle_id for item in snapshot["obstacles"])

        deleted = client.delete(f"/api/layout/obstacles/{obstacle_id}")
        assert deleted.status_code == 204