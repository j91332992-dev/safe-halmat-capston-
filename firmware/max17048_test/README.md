# MAX17048 단독 시험 (ESP-IDF v5.5.5, DFR1172 ESP32-P4)

이 프로젝트는 MAX17048만 시험합니다. Wi-Fi, 서버, 카메라, 마이크, 스피커, UWB는 시작하지 않습니다.

## 이 프로젝트가 사용하는 배선

| MAX17048 | DFR1172 / 배터리 연결 |
| --- | --- |
| `SDA` | P2 `GPIO33` |
| `SCL` | P2 `GPIO32` |
| `VIN` 또는 `VDD` | DFR1172 `3V3` |
| 배터리 JST `+/-` | SW6106 `B+ / B-`와 같은 배터리 `+/-` 선 |
| `ALRT/INT/QStart` | 연결하지 않음 |

MAX17048의 논리 전원(`VIN` 또는 `VDD`)에는 5V를 연결하지 않습니다. SW6106의 USB-A 5V 출력도 MAX17048의 배터리 측정용 JST에 연결하지 않습니다.

## 빌드와 업로드

1. VS Code에서 이 `firmware/max17048_test` 폴더를 엽니다.
2. `Ctrl+Shift+P`를 누르고 `ESP-IDF: Open ESP-IDF Terminal`을 선택합니다.
3. 아래 명령을 순서대로 실행합니다. `COM7`은 장치 관리자에서 확인한 DFR1172의 실제 COM 번호로 바꿉니다.

```powershell
idf.py set-target esp32p4
idf.py build
idf.py -p COM7 flash monitor
```

`flash monitor`가 끝난 뒤에도 시리얼 모니터는 계속 열려 있습니다. 종료할 때는 `Ctrl+]`를 누릅니다.

## 정상 로그

부팅 후 아래 형태의 로그가 나와야 합니다.

```text
I (...) MAX17048_TEST: I2C response: 0x36  <-- expected MAX17048
I (...) MAX17048_TEST: MAX17048 version register: 0x....
I (...) MAX17048_TEST: BATTERY: voltage=4.021 V, SOC=82.4 %
```

- `0x36` 응답: P4와 MAX17048 사이의 I2C 통신이 확인된 상태입니다.
- `voltage`: MAX17048이 읽은 배터리 셀 전압입니다. SW6106 `B+`와 `B-`에서 멀티미터로 잰 값과 비교합니다.
- `SOC`: MAX17048이 계산한 배터리 잔량입니다.

## 오류 로그

`MAX17048 was not found at 0x36`이 반복되면 DFR1172의 3.3V, 공통 GND, SDA=GPIO33, SCL=GPIO32, MAX17048 배터리 JST 연결을 확인합니다.

`Read failed`가 나오면 주소는 응답했지만 레지스터를 읽지 못한 상태입니다. 전원과 SDA/SCL 납땜 상태를 다시 확인합니다.
