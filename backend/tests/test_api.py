from fastapi.testclient import TestClient

from app.main import app


def test_health_snapshot_starts_in_hardware_mode_and_offline():
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["mode"] == "hardware"
        snapshot = client.get("/api/dashboard/snapshot")
        assert snapshot.status_code == 200
        data = snapshot.json()
        assert len(data["anchors"]) == 4
        assert data["workers"][0]["worker_id"] == "worker-001"
        assert not any(item["online"] for item in data["devices"])
        assert not any(item["online"] for item in data["anchors"])
        assert all(item.get("last_seen") for item in data["anchors"])


def test_real_heartbeat_is_the_only_way_to_mark_device_online():
    with TestClient(app) as client:
        response = client.post(
            "/api/devices/heartbeat",
            json={
                "worker_id": "worker-001",
                "helmet_id": "helmet-001",
                "device_id": "helmet-001-av",
                "rssi": -48,
                "battery": 77,
                "component_status": {"camera": "ready", "mic": "ready", "speaker": "ready"},
            },
        )
        assert response.status_code == 200
        assert response.json()["server_mode"] == "hardware"
        assert response.json()["device"]["online"] is True
        snapshot = client.get("/api/dashboard/snapshot").json()
        av = next(item for item in snapshot["devices"] if item["device_id"] == "helmet-001-av")
        assert av["online"] is True
        assert av["battery"] == 77


def test_mock_scenario_endpoint_is_removed():
    with TestClient(app) as client:
        response = client.post("/api/system/mock/scenario", json={"scenario": "fire", "worker_id": "worker-001"})
        assert response.status_code == 404


def test_uwb_packet_marks_only_measured_anchors_online():
    with TestClient(app) as client:
        response = client.post(
            "/api/uwb/distances",
            json={
                "worker_id": "worker-001",
                "helmet_id": "helmet-001",
                "device_id": "helmet-001-uwb",
                "uwb_tag_id": "tag-001",
                "distances_calibrated": True,
                "measurements": [
                    {"anchor_id": "anchor-001", "distance_m": 3.606, "quality": 1.0},
                    {"anchor_id": "anchor-002", "distance_m": 4.842, "quality": 1.0},
                    {"anchor_id": "anchor-003", "distance_m": 6.440, "quality": 1.0},
                ],
            },
        )
        assert response.status_code == 200
        snapshot = client.get("/api/dashboard/snapshot").json()
        states = {item["anchor_id"]: item["online"] for item in snapshot["anchors"]}
        assert states == {
            "anchor-001": True,
            "anchor-002": True,
            "anchor-003": True,
            "anchor-004": False,
        }
        tag = next(item for item in snapshot["devices"] if item["device_id"] == "helmet-001-uwb")
        assert tag["online"] is True
