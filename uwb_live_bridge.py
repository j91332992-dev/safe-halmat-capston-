"""Makerfabs DW3000 TAG 시리얼 출력을 FastAPI 실시간 위치 API로 전달합니다."""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
from dataclasses import dataclass
import json
from pathlib import Path
import re
from statistics import median
import sys
import time

import requests
import serial
from serial import SerialException


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CALIBRATION_FILE = PROJECT_ROOT / "uwb_calibration.json"
ANCHOR_ID_MAP = {
    0: "anchor-001",
    1: "anchor-002",
    2: "anchor-003",
    3: "anchor-004",
}
TAG_LINE_RE = re.compile(
    r"T(?P<tag>\d+),mask:(?P<mask>[0-9A-F]+),seq:(?P<seq>\d+),"
    r"(?:beacon:(?P<beacon>\d+)|fail:(?P<fail>\d+)),range:\((?P<ranges>[^)]*)\),"
    r"ancid:\((?P<anchor_ids>[^)]*)\)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TagFrame:
    tag_id: int
    mask: int
    sequence: int
    beacon: int
    ranges_cm: tuple[int, ...]
    anchor_numbers: tuple[int, ...]


def _parse_csv_ints(value: str) -> tuple[int, ...]:
    return tuple(int(item.strip()) for item in value.split(","))


def parse_tag_line(line: str) -> TagFrame | None:
    """펌웨어 한 줄을 파싱합니다. 부팅 로그 등 다른 줄은 None입니다."""
    match = TAG_LINE_RE.search(line.strip())
    if not match:
        return None
    ranges_cm = _parse_csv_ints(match.group("ranges"))
    anchor_numbers = _parse_csv_ints(match.group("anchor_ids"))
    if len(ranges_cm) != len(anchor_numbers):
        return None
    return TagFrame(
        tag_id=int(match.group("tag")),
        mask=int(match.group("mask"), 16),
        sequence=int(match.group("seq")),
        beacon=int(match.group("beacon")) if match.group("beacon") is not None else -1,
        ranges_cm=ranges_cm,
        anchor_numbers=anchor_numbers,
    )


def load_calibration(path: Path, disabled: bool = False) -> dict[str, float]:
    if disabled:
        return {anchor_id: 0.0 for anchor_id in ANCHOR_ID_MAP.values()}
    data = json.loads(path.read_text(encoding="utf-8"))
    offsets = data.get("offset_m", data)
    return {
        anchor_id: float(offsets.get(anchor_id, 0.0))
        for anchor_id in ANCHOR_ID_MAP.values()
    }


class DistanceProcessor:
    """최근 거리 중앙값과 앵커별 보정을 적용합니다."""

    def __init__(self, calibration: dict[str, float], history_size: int = 5, anchor_hold_seconds: float = 2.5):
        self.calibration = calibration
        self.history = defaultdict(lambda: deque(maxlen=history_size))
        self.last_seen: dict[str, float] = {}
        self.anchor_hold_seconds = anchor_hold_seconds

    def process(self, frame: TagFrame) -> list[dict]:
        now = time.monotonic()
        current: dict[str, int] = {}
        for raw_cm, anchor_number in zip(frame.ranges_cm, frame.anchor_numbers):
            anchor_id = ANCHOR_ID_MAP.get(anchor_number)
            if anchor_id is None or raw_cm <= 0:
                continue
            current[anchor_id] = raw_cm
            self.history[anchor_id].append(raw_cm)
            self.last_seen[anchor_id] = now

        measurements = []
        recent_anchor_ids = {
            anchor_id for anchor_id, seen_at in self.last_seen.items()
            if now - seen_at <= self.anchor_hold_seconds
        }
        for anchor_id in sorted(recent_anchor_ids):
            samples = self.history[anchor_id]
            smoothed_cm = float(median(samples))
            distance_m = max(0.05, smoothed_cm / 100.0 + self.calibration.get(anchor_id, 0.0))
            spread_cm = max(samples) - min(samples) if len(samples) > 1 else 0
            age = now - self.last_seen[anchor_id]
            held_penalty = 0.15 if anchor_id not in current else 0.0
            age_penalty = held_penalty + min(
                0.20, age / max(0.001, self.anchor_hold_seconds) * 0.20
            )
            quality = max(0.40, min(0.99, 0.98 - spread_cm / 250.0 - age_penalty))
            measurements.append(
                {
                    "anchor_id": anchor_id,
                    "distance_m": round(distance_m, 3),
                    "quality": round(quality, 2),
                }
            )
        return measurements


class BackendClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.last_heartbeat = 0.0

    def wait_until_ready(self, timeout_seconds: int = 60) -> None:
        print(f"[서버] {self.base_url} 연결 대기 중...")
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                response = self.session.get(f"{self.base_url}/api/health", timeout=2)
                if response.ok:
                    self.session.post(
                        f"{self.base_url}/api/system/mode",
                        json={"mode": "hardware"},
                        timeout=2,
                    ).raise_for_status()
                    print("[서버] 연결 완료, hardware 모드로 전환했습니다.")
                    return
            except requests.RequestException:
                pass
            time.sleep(1)
        raise RuntimeError("60초 동안 백엔드에 연결하지 못했습니다. run_backend.bat을 확인하세요.")

    def heartbeat_if_due(self) -> None:
        now = time.monotonic()
        if now - self.last_heartbeat < 10:
            return
        payload = {
            "organization_id": "org-001",
            "site_id": "site-001",
            "worker_id": "worker-001",
            "helmet_id": "helmet-001",
            "device_id": "helmet-001-uwb",
            "battery": None,
            "component_status": {"uwb": "ready", "serial_bridge": "ready"},
        }
        self.session.post(
            f"{self.base_url}/api/devices/heartbeat", json=payload, timeout=3
        ).raise_for_status()
        self.last_heartbeat = now

    def send_distances(self, tag_id: int, measurements: list[dict]) -> dict:
        payload = {
            "organization_id": "org-001",
            "site_id": "site-001",
            "worker_id": "worker-001",
            "helmet_id": "helmet-001",
            "device_id": "helmet-001-uwb",
            "uwb_tag_id": f"tag-{tag_id + 1:03d}",
            "measurements": measurements,
        }
        response = self.session.post(
            f"{self.base_url}/api/uwb/distances", json=payload, timeout=3
        )
        response.raise_for_status()
        return response.json()


def run_bridge(args: argparse.Namespace) -> None:
    calibration = load_calibration(args.calibration, args.no_calibration)
    processor = DistanceProcessor(calibration, args.history_size, args.anchor_hold_seconds)
    backend = BackendClient(args.api_url)
    backend.wait_until_ready()
    print(f"[보정] {calibration}")
    print(f"[시리얼] {args.port} @ {args.baud} 연결 중...")
    print("[안내] 종료하려면 Ctrl+C를 누르세요.")

    last_post = 0.0
    while True:
        try:
            with serial.Serial(args.port, args.baud, timeout=1) as port:
                port.reset_input_buffer()
                print(f"[시리얼] {args.port} 연결 완료")
                while True:
                    raw = port.readline()
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="replace").strip()
                    frame = parse_tag_line(line)
                    if frame is None:
                        if args.show_raw and line:
                            print(f"[TAG] {line}")
                        continue
                    measurements = processor.process(frame)
                    if len(measurements) < 3:
                        print(f"[건너뜀] seq={frame.sequence}, 유효 앵커={len(measurements)}")
                        continue
                    now = time.monotonic()
                    if now - last_post < args.post_interval:
                        continue
                    try:
                        backend.heartbeat_if_due()
                        result = backend.send_distances(frame.tag_id, measurements)
                    except requests.RequestException as exc:
                        print(f"[서버 오류] {exc}")
                        time.sleep(1)
                        continue
                    last_post = now
                    location = result["location"]
                    distances = " ".join(
                        f"{item['anchor_id'][-1]}={item['distance_m']:.2f}m"
                        for item in measurements
                    )
                    print(
                        f"[위치] x={location['x']:.2f}m y={location['y']:.2f}m "
                        f"신뢰={location['confidence']:.2f} | {distances}"
                    )
        except SerialException as exc:
            print(f"[시리얼 오류] {exc} — 2초 후 다시 연결합니다.")
            time.sleep(2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UWB TAG 시리얼 데이터를 실시간 웹 지도로 전송")
    parser.add_argument("--port", default="COM6", help="TAG COM 포트 (기본: COM6)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION_FILE)
    parser.add_argument("--no-calibration", action="store_true")
    parser.add_argument("--history-size", type=int, default=5)
    parser.add_argument("--anchor-hold-seconds", type=float, default=2.5)
    parser.add_argument("--post-interval", type=float, default=0.2)
    parser.add_argument("--show-raw", action="store_true")
    return parser


def main() -> int:
    try:
        run_bridge(build_parser().parse_args())
    except KeyboardInterrupt:
        print("\n[종료] UWB 실시간 위치 연결을 종료했습니다.")
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
