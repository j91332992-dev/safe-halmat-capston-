from __future__ import annotations

import getpass
import ipaddress
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "firmware" / "helmet_av_device" / "include" / "device_secrets.h"


def c_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def main() -> None:
    print("안전모 AV 장치와 서버 PC가 함께 사용할 Wi-Fi/서버 정보를 입력하세요.")
    ssid = input("Wi-Fi 이름(SSID): ").strip()
    password = getpass.getpass("Wi-Fi 비밀번호(화면에 표시되지 않음): ")
    server_ip = input("서버 PC IPv4 [192.168.0.31]: ").strip() or "192.168.0.31"
    if not ssid:
        raise SystemExit("SSID는 비워 둘 수 없습니다.")
    ipaddress.ip_address(server_ip)
    content = f'''#pragma once
#define WIFI_SSID "{c_string(ssid)}"
#define WIFI_PASSWORD "{c_string(password)}"
#define SERVER_BASE_URL "http://{server_ip}:8000"
#define SERVER_HOST "{server_ip}"
#define SERVER_PORT 8000
'''
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"[완료] {OUTPUT}")
    print(f"서버 주소: http://{server_ip}:8000")
    print("다음 단계: helmet_av_device 펌웨어를 업로드하세요.")


if __name__ == "__main__":
    main()