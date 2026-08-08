import argparse
import random
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
IMAGES = ROOT / "sample_data" / "test_images"


def main() -> None:
    parser = argparse.ArgumentParser(description="한미르 카메라 프레임 모의 전송기")
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--device", default="helmet-001-av")
    parser.add_argument("--worker", default="worker-001")
    parser.add_argument("--helmet", default="helmet-001")
    parser.add_argument("--interval", type=float, default=3.0)
    args = parser.parse_args()
    images = list(IMAGES.glob("*.jpg"))
    if not images:
        raise SystemExit(f"테스트 이미지가 없습니다: {IMAGES}")
    print(f"[CAMERA MOCK] {len(images)}개 이미지 -> {args.server}, Ctrl+C로 종료")
    while True:
        image = random.choice(images)
        try:
            with image.open("rb") as stream:
                response = requests.post(
                    f"{args.server}/api/camera/frame",
                    files={"file": (image.name, stream, "image/jpeg")},
                    data={"device_id": args.device, "worker_id": args.worker, "helmet_id": args.helmet},
                    timeout=60,
                )
            response.raise_for_status()
            analysis = response.json().get("details", {}).get("analysis", {})
            print(f"[전송 성공] {image.name} mode={analysis.get('mode')} ppe={analysis.get('ppe')}")
        except requests.RequestException as exc:
            print(f"[전송 실패] {exc}")
        time.sleep(max(0.3, args.interval))


if __name__ == "__main__":
    main()