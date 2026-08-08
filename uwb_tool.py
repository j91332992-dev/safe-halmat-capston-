"""Makerfabs UWB 펌웨어를 한글 경로 문제 없이 빌드·업로드하는 도구."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_LIBRARY = PROJECT_ROOT / "firmware" / "lib" / "Dw3000"
SOURCE_PROJECTS = {
    "range": PROJECT_ROOT / "firmware" / "uwb_range_test",
    "multi": PROJECT_ROOT / "firmware" / "uwb_multi_test",
}
BUILD_ENVS = {
    "range": ("tag", "anchor"),
    "multi": ("tag", "anchor-01", "anchor-02", "anchor-03", "anchor-04"),
}
ROLE_PROFILE = {
    "tag": ("range", "tag"),
    "anchor": ("range", "anchor"),
    "tag-multi": ("multi", "tag"),
    "anchor-01": ("multi", "anchor-01"),
    "anchor-02": ("multi", "anchor-02"),
    "anchor-03": ("multi", "anchor-03"),
    "anchor-04": ("multi", "anchor-04"),
}
ASCII_ROOT = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Temp" / "hanmir-uwb"
STAGED_LIBRARY = ASCII_ROOT / "lib" / "Dw3000"
PLATFORMIO_CORE = ASCII_ROOT / ".platformio"


def _safe_remove(path: Path) -> None:
    root = ASCII_ROOT.resolve()
    resolved = path.resolve()
    if resolved == root or root not in resolved.parents:
        raise RuntimeError(f"안전하지 않은 임시 경로 삭제 거부: {resolved}")
    if path.exists():
        shutil.rmtree(path)


def stage_sources(profile: str) -> Path:
    source_project = SOURCE_PROJECTS[profile]
    staged_project = ASCII_ROOT / source_project.name
    if not source_project.is_dir() or not SOURCE_LIBRARY.is_dir():
        raise FileNotFoundError("UWB 프로젝트 또는 DW3000 라이브러리가 없습니다.")
    ASCII_ROOT.mkdir(parents=True, exist_ok=True)
    _safe_remove(staged_project)
    _safe_remove(STAGED_LIBRARY)
    shutil.copytree(source_project, staged_project, ignore=shutil.ignore_patterns(".pio", "__pycache__"))
    STAGED_LIBRARY.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE_LIBRARY, STAGED_LIBRARY, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    print(f"[준비] {profile} 영문 빌드 경로: {staged_project}")
    return staged_project


def run_platformio(arguments: list[str], cwd: Path | None = None) -> int:
    env = os.environ.copy()
    env["PLATFORMIO_CORE_DIR"] = str(PLATFORMIO_CORE)
    command = [sys.executable, "-m", "platformio", *arguments]
    print("[실행]", " ".join(command))
    return subprocess.run(command, cwd=cwd, env=env, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="한미르 UWB 펌웨어 빌드/업로드 도구")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="선택한 펌웨어 묶음을 빌드")
    build.add_argument("--profile", choices=tuple(SOURCE_PROJECTS), default="range")

    upload = subparsers.add_parser("upload", help="지정한 보드에 펌웨어 업로드")
    upload.add_argument("--role", choices=tuple(ROLE_PROFILE), required=True)
    upload.add_argument("--port", required=True, help="예: COM6")

    monitor = subparsers.add_parser("monitor", help="시리얼 로그 확인")
    monitor.add_argument("--port", required=True, help="예: COM6")

    args = parser.parse_args()
    if args.command == "monitor":
        return run_platformio(["device", "monitor", "--port", args.port, "--baud", "115200"])

    if args.command == "build":
        staged_project = stage_sources(args.profile)
        arguments = ["run"]
        for environment in BUILD_ENVS[args.profile]:
            arguments.extend(("-e", environment))
        return run_platformio(arguments, staged_project)

    profile, environment = ROLE_PROFILE[args.role]
    staged_project = stage_sources(profile)
    return run_platformio(
        ["run", "-e", environment, "--target", "upload", "--upload-port", args.port],
        staged_project,
    )


if __name__ == "__main__":
    raise SystemExit(main())
