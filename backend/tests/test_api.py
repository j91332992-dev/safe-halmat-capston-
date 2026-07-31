from fastapi.testclient import TestClient

from app.main import app


def test_health_and_snapshot():
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        snapshot = client.get("/api/dashboard/snapshot")
        assert snapshot.status_code == 200
        data = snapshot.json()
        assert len(data["anchors"]) == 4
        assert data["workers"][0]["worker_id"] == "worker-001"


def test_mock_scenario_changes_risk():
    with TestClient(app) as client:
        response = client.post("/api/system/mock/scenario", json={"scenario": "fire", "worker_id": "worker-001"})
        assert response.status_code == 200
        assert response.json()["worker"]["risk_score"] >= 50

