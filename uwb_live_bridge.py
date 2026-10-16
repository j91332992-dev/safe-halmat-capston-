"""Makerfabs DW3000 TAG 시리얼 출력을 FastAPI 실시간 위치 API로 전달합니다."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
import time
from datetime import datetime, timezone
from queue import Queue, Full, Empty
from threading import Thread, Event
from uuid import uuid4

from backend.app.services.uwb_log_service import BoundedJsonlLog

import requests
import serial
from serial import SerialException


PROJECT_ROOT = Path(__file__).resolve().parent
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
    payload: dict | None = None


def _parse_csv_ints(value: str) -> tuple[int, ...]:
    return tuple(int(item.strip()) for item in value.split(","))


def parse_tag_line(line: str) -> TagFrame | None:
    """펌웨어 한 줄을 파싱합니다. 부팅 로그 등 다른 줄은 None입니다."""
    if line.strip().startswith("{"):
        try:
            data = json.loads(line)
            if data.get("schema_version") != 2:
                return None
            # Use the same validation as the Wi-Fi endpoint. Preserve firmware
            # JSON, including raw diagnostics, instead of re-deriving them here.
            from backend.app.schemas.api import UwbDistancesIn
            validated = UwbDistancesIn.model_validate(data)
            if not validated.session_id or not validated.measurement_id or validated.sequence is None:
                return None
            observations = validated.observations
            numbers = tuple(int(item.anchor_id[-3:]) - 1 for item in observations)
            return TagFrame(
                tag_id=validated.tag_hw_id or 0,
                mask=sum(1 << number for number, item in zip(numbers, observations)
                         if number in ANCHOR_ID_MAP and item.status != "missing"),
                sequence=validated.sequence, beacon=-1,
                ranges_cm=tuple(item.legacy_range_cm or 0 for item in observations),
                anchor_numbers=numbers, payload=data,
            )
        except (ValueError, TypeError, KeyError):
            return None
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


def raw_measurements(frame: TagFrame) -> list[dict]:
    """No calibration, filtering, hold, or quality inference in the bridge."""
    if frame.payload is not None:
        return frame.payload["measurements"]
    return [{"anchor_id": ANCHOR_ID_MAP[number], "distance_m": cm / 100.0}
            for cm, number in zip(frame.ranges_cm, frame.anchor_numbers)
            if number in ANCHOR_ID_MAP and cm > 0]


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

    def send_payload(self, payload: dict) -> dict:
        response = self.session.post(
            f"{self.base_url}/api/uwb/distances", json=payload, timeout=3
        )
        response.raise_for_status()
        return response.json()

    def send_distances(self, tag_id: int, measurements: list[dict]) -> dict:
        return self.send_payload({
            "organization_id": "org-001",
            "site_id": "site-001",
            "worker_id": "worker-001",
            "helmet_id": "helmet-001",
            "device_id": "helmet-001-uwb",
            "uwb_tag_id": f"tag-{tag_id + 1:03d}",
            "measurements": measurements,
        })


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_cycle_payload(frame: TagFrame, measurements: list[dict], received_at: str) -> dict:
    payload = dict(frame.payload or {
        "worker_id": "worker-001", "helmet_id": "helmet-001",
        "device_id": "helmet-001-uwb", "uwb_tag_id": f"tag-{frame.tag_id + 1:03d}",
        "sequence": frame.sequence % 256, "time_basis": "legacy_unknown",
    })
    payload.update(transport="usb", bridge_received_at=received_at,
                   measurements=measurements)
    if frame.payload is None:
        payload["distances_calibrated"] = False
    return payload


def capture_frames(port, args, log, backend=None) -> None:
    """Serial reading never waits for HTTP. Log every frame before throttling."""
    queue = Queue(maxsize=32)
    stopping = Event()

    def sender():
        while not stopping.is_set():
            try:
                capture_id, payload = queue.get(timeout=0.1)
            except Empty:
                continue
            record = {"event": "usb_delivery", "capture_id": capture_id,
                      "measurement_id": payload.get("measurement_id"), "sent_at": utc_timestamp()}
            try:
                backend.heartbeat_if_due()
                result = backend.send_payload(payload)
                record.update(status="sent", result=result)
            except requests.RequestException as exc:
                response = exc.response
                record.update(status="failed", error=str(exc),
                              http_status=response.status_code if response is not None else None,
                              response=response.text[:2048] if response is not None else None)
            log.append(record)
            queue.task_done()

    thread = Thread(target=sender, daemon=True) if backend is not None else None
    if thread:
        thread.start()
    last_post = 0.0
    try:
        while True:
            raw = port.readline()
            if not raw:
                continue
            received_at = utc_timestamp()
            line = raw.decode("utf-8", errors="replace").strip()
            frame = parse_tag_line(line)
            if frame is None:
                if line.startswith("{"):
                    log.append({"event": "usb_parse_failed", "received_at": received_at, "line": line[:16384]})
                if args.show_raw and line:
                    print(f"[TAG] {line}")
                continue
            measurements = raw_measurements(frame)
            payload = build_cycle_payload(frame, measurements, received_at)
            capture_id = uuid4().hex
            payload["bridge_capture_id"] = capture_id
            now = time.monotonic()
            action = "log_only" if backend is None else "throttled" if now - last_post < args.post_interval else "queued"
            # Preserve firmware values identically on USB and Wi-Fi.
            log.append({"event": "usb_cycle", "capture_id": capture_id,
                        "received_at": received_at, "firmware": frame.payload,
                        "legacy_line": line if frame.payload is None else None,
                        "payload": payload, "delivery": action,
                        "condition": args.condition, "run_label": args.run_label})
            if action == "queued":
                try:
                    queue.put_nowait((capture_id, payload))
                    last_post = now
                except Full:
                    log.append({"event": "usb_delivery", "capture_id": capture_id,
                                "measurement_id": payload.get("measurement_id"), "status": "queue_full"})
    finally:
        stopping.set()
        if thread:
            # At most one heartbeat + POST remains in flight (3 s each).
            thread.join(timeout=7)
            while not queue.empty():
                capture_id, payload = queue.get_nowait()
                log.append({"event": "usb_delivery", "capture_id": capture_id,
                            "measurement_id": payload.get("measurement_id"), "status": "connection_closed"})


def run_bridge(args: argparse.Namespace) -> None:
    if args.post_interval < 0:
        raise ValueError("post-interval >= 0 required")
    log = BoundedJsonlLog(args.log_path, args.log_max_bytes, args.log_backups, args.log_retention_days)
    backend = None
    if not args.log_only:
        backend = BackendClient(args.api_url)
        backend.wait_until_ready()
    print("[거리 처리] 서버 공통 보정·중앙값 필터 사용")
    print(f"[시리얼] {args.port} @ {args.baud}; 로그={args.log_path}; log_only={args.log_only}")
    while True:
        try:
            with serial.Serial(args.port, args.baud, timeout=1) as port:
                # Do not discard buffered first cycles/session information.
                capture_frames(port, args, log, backend)
        except SerialException as exc:
            log.append({"event": "usb_disconnect", "received_at": utc_timestamp(), "error": str(exc)})
            print(f"[시리얼 오류] {exc} — 2초 후 다시 연결합니다.")
            time.sleep(2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UWB TAG 시리얼 데이터를 실시간 웹 지도로 전송")
    parser.add_argument("--port", default="COM6", help="TAG COM 포트 (기본: COM6)")
    parser.add_argument("--baud", type=int, default=460800, help="새 TAG: 460800; 기존 펌웨어/앵커: 115200")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--post-interval", type=float, default=0.0)
    parser.add_argument("--show-raw", action="store_true")
    parser.add_argument("--log-only", action="store_true", help="서버 연결/heartbeat/전송 없이 수집")
    parser.add_argument("--log-path", type=Path, default=PROJECT_ROOT / "logs" / "uwb-usb.jsonl")
    parser.add_argument("--log-max-bytes", type=int, default=10 * 1024 * 1024)
    parser.add_argument("--log-backups", type=int, default=4)
    parser.add_argument("--log-retention-days", type=float, default=7)
    parser.add_argument("--condition", choices=("los", "body", "obstacle", "unspecified"), default="unspecified")
    parser.add_argument("--run-label", default="")
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
