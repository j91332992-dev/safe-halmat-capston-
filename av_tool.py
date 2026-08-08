from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PIO_CORE = Path.home() / ".platformio"


def run_subst(letter: str, target: Path | None = None) -> None:
    command = ["subst", f"{letter}:"]
    command += [str(target)] if target else ["/D"]
    subprocess.run(command, check=True, capture_output=True, text=True)


def mapped_platformio(args: list[str]) -> int:
    if Path("P:/").exists() or Path("Q:/").exists():
        raise SystemExit("P: 또는 Q: 드라이브가 이미 사용 중입니다. 비운 뒤 다시 실행하세요.")
    run_subst("P", PIO_CORE)
    try:
        run_subst("Q", ROOT)
        try:
            env = os.environ.copy()
            env["PLATFORMIO_CORE_DIR"] = "P:\\"
            command = [sys.executable, "-m", "platformio", "run", "-d", "Q:\\firmware\\helmet_av_device", *args]
            print("[실행]", " ".join(command))
            return subprocess.run(command, env=env).returncode
        finally:
            run_subst("Q")
    finally:
        run_subst("P")


def main() -> None:
    parser = argparse.ArgumentParser(description="한글 경로 대응 안전모 AV PlatformIO 도구")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build", help="펌웨어 컴파일")
    upload = sub.add_parser("upload", help="펌웨어 컴파일 후 업로드")
    upload.add_argument("--port", required=True, help="예: COM6")
    monitor = sub.add_parser("monitor", help="시리얼 모니터")
    monitor.add_argument("--port", required=True)
    monitor.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()
    if args.command == "build":
        code = mapped_platformio([])
    elif args.command == "upload":
        code = mapped_platformio(["-t", "upload", "--upload-port", args.port])
    else:
        code = subprocess.run([sys.executable, "-m", "platformio", "device", "monitor", "--port", args.port, "--baud", str(args.baud), "--dtr", "0", "--rts", "0"]).returncode
    raise SystemExit(code)


if __name__ == "__main__":
    main()
