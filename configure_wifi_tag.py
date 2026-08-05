"""TAG Wi-Fi 비밀설정을 안전하게 생성합니다. 비밀번호는 화면에 표시하지 않습니다."""
from __future__ import annotations

from getpass import getpass
from pathlib import Path
import socket


PROJECT_ROOT = Path(__file__).resolve().parent
SECRETS_FILE = PROJECT_ROOT / "firmware" / "uwb_multi_test" / "include" / "wifi_secrets.h"


def detect_local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "192.168.0.10"
    finally:
        sock.close()


def cpp_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def main() -> None:
    print("TAG와 컴퓨터가 함께 사용할 2.4GHz Wi-Fi 정보를 입력하세요.")
    ssid = input("Wi-Fi 이름(SSID): ").strip()
    if not ssid:
        raise SystemExit("SSID는 비워둘 수 없습니다.")
    password = getpass("Wi-Fi 비밀번호(화면에 표시되지 않음): ")
    detected_ip = detect_local_ip()
    server_ip = input(f"서버 PC IPv4 [{detected_ip}]: ").strip() or detected_ip
    server_url = f"http://{server_ip}:8000/api/uwb/distances"
    content = f'''#pragma once

// configure_wifi_tag.py가 생성한 로컬 전용 파일입니다. GitHub에 포함하지 않습니다.
#define HANMIR_WIFI_SSID "{cpp_string(ssid)}"
#define HANMIR_WIFI_PASSWORD "{cpp_string(password)}"
#define HANMIR_SERVER_URL "{cpp_string(server_url)}"
'''
    SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SECRETS_FILE.write_text(content, encoding="utf-8")
    print("[완료] TAG Wi-Fi 설정을 저장했습니다.")
    print(f"  서버 주소: {server_url}")
    print("  다음 단계: TAG 펌웨어를 다시 업로드하세요.")


if __name__ == "__main__":
    main()