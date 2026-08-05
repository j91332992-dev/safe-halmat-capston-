"""최종 통합 서버에 실제 장치와 같은 API로 데이터를 보내는 mock 발생기."""
import itertools
import math
import random
import sys
import time

import requests


BASE_URL = "http://127.0.0.1:8000"
COMMON = {
    "organization_id": "org-001",
    "site_id": "site-001",
    "worker_id": "worker-001",
    "helmet_id": "helmet-001",
}
ANCHORS = {
    "anchor-001": (0.0, 0.0),
    "anchor-002": (5.8, 0.0),
    "anchor-003": (5.8, 8.2),
    "anchor-004": (0.0, 8.2),
}
PATH = [
    (0.8, 1.0),
    (2.0, 1.2),
    (3.5, 1.5),
    (4.6, 2.0),
    (5.0, 3.5),
    (4.7, 5.6),
    (4.5, 6.5),
    (3.0, 7.0),
    (1.5, 6.0),
    (0.8, 4.0),
]


def post(path: str, payload: dict) -> dict:
    response = requests.post(f"{BASE_URL}{path}", json=payload, timeout=5)
    response.raise_for_status()
    return response.json()


def wait_for_server() -> None:
    print("[시뮬레이터] 백엔드 연결 대기 중...")
    for _ in range(60):
        try:
            if requests.get(f"{BASE_URL}/api/health", timeout=2).ok:
                print("[시뮬레이터] 백엔드 연결 성공")
                return
        except requests.RequestException:
            time.sleep(1)
    raise RuntimeError("60초 동안 백엔드에 연결하지 못했습니다.")


def register_devices() -> None:
    for device_id, device_type in (("helmet-001-av", "assistant_device"), ("helmet-001-uwb", "position_device")):
        post(
            "/api/devices/register",
            {**COMMON, "device_id": device_id, "device_type": device_type, "firmware_version": "simulator-0.1.0", "ip": "127.0.0.1", "mac": "MOCK"},
        )


def run() -> None:
    wait_for_server()
    register_devices()
    print("[시뮬레이터] Ctrl+C로 종료할 수 있습니다.")
    for tick, (x, y) in enumerate(itertools.cycle(PATH), start=1):
        for device_id in ("helmet-001-av", "helmet-001-uwb"):
            post(
                "/api/devices/heartbeat",
                {
                    **COMMON,
                    "device_id": device_id,
                    "rssi": random.randint(-67, -48),
                    "battery": max(12, 92 - tick * 0.03),
                    "component_status": {"camera": "ready", "mic": "ready", "speaker": "ready", "button": "ready", "uwb": "ready"},
                },
            )
        measurements = [
            {
                "anchor_id": anchor_id,
                "distance_m": round(math.hypot(x - ax, y - ay) + random.uniform(-0.08, 0.08), 3),
                "quality": round(random.uniform(0.84, 0.99), 2),
            }
            for anchor_id, (ax, ay) in ANCHORS.items()
        ]
        result = post(
            "/api/uwb/distances",
            {**COMMON, "device_id": "helmet-001-uwb", "uwb_tag_id": "tag-001", "measurements": measurements},
        )
        if tick % 15 == 0:
            post("/api/camera/mock-detection", {"worker_id": "worker-001", "device_id": "helmet-001-av", "vest": True, "glove": tick % 30 != 0, "fire": False, "smoke": False})
        if tick % 25 == 0:
            post("/api/audio/mock-command", {"worker_id": "worker-001", "device_id": "helmet-001-av", "text": "현재 위험도 알려줘"})
        worker = result["worker"]
        print(f"[시뮬레이터] 위치=({worker['x']:.2f}, {worker['y']:.2f}) 위험도={worker['risk_score']} {worker['risk_level']}")
        time.sleep(1)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n[시뮬레이터] 종료했습니다.")
    except Exception as exc:
        print(f"[시뮬레이터 오류] {exc}")
        sys.exit(1)

