# HANMIR ESP32-P4 신규 HW — 최종 배선표

작성일: 2026-10-01
요약: 새 HW 설계와 기존 대비 교체·추가·유지 부품, 배선 변화를 정리한 문서입니다.

**표시:** **[확정]** 자료·사진 확인 완료 / **[단위시험 필요]** 연결 후 기능 시험 / **[실물 확인 필요]** 제품 표기·정격 확인 뒤 연결

## 1. 최종 부품표

| 부품 | 역할 | 전원 | 통신 | 상태 |
|---|---|---|---|---|
| DFR1172 ESP32-P4 | 카메라·음성·통신 제어 | `VCC` 5V | MIPI CSI, I2S, I2C, UART, 내장 C6 | 신규 **[확정]** |
| OV5647 + FPC | 영상 입력 | CSI 커넥터 공급 | MIPI CSI, SCCB(I2C) | 신규 **[확정]** |
| DTP105085 1S 3.7V 5000mAh | 시스템 전원 | 배터리 | - | 유지 |
| SW6106 | USB-C 충전, USB-A 5V 출력 | `B+`, `B-` | - | 신규 **[확정]** |
| 푸시락 LED 스위치 | 시스템 5V ON/OFF·표시 | 5V | - | 신규 |
| MAX17048 | 배터리 전압·SOC 측정 전용 | 배터리 측 + 3.3V 논리 | I2C | 신규 **[확정]** |
| INMP441 | 입 가까이의 주 마이크 | 3.3V | I2S RX | 유지 |
| MAX98357A + 8Ω 스피커 | 음성 출력 | 5V | I2S TX | 유지 |
| BNO085 | 낙상·가속도·자이로·자세 데이터 | 3.3V | 표준 UART | 신규 **[단위시험 필요]** |
| 기존 UWB 태그 | 위치 데이터 자체 전송 | 5V | P4 데이터선 없음 | 유지 **[확정]** |
| UWB 앵커 | 위치 기준점 | 현장 별도 설치 | UWB | 안전모 내부 배선 없음 |
| microSD | 영상·로그 저장 시 사용 | 보드 내장 | SDIO | 선택, 외부 배선 없음 |
| ESP32-C5 | 5GHz 필요 시만 사용 | - | - | 예비, 초기 미연결 |

## 2. 전원 배선표

모든 부품은 핀헤더를 끼우지 않고 **보드의 해당 납땜 홀에 전선을 직접 납땜**한다. 단, MAX17048의 배터리 측정 연결만 JST-PH 케이블을 보드에 꽂고, 케이블 반대쪽을 아래 공통선에 직접 납땜한다. 22AWG 공통선은 짧게 만들고 한 접합점에는 최대 2~3개만 분기한다.

| 공통 전원선 | 시작·끝 | 분기 대상 | 전압 | 선 | 직접 납땜 방법 |
|---|---|---|---:|---|---|
| 배터리 `+` 공통선 | 배터리 `+` → SW6106 `B+` | MAX17048 JST-PH 케이블 `+` | 배터리 전압 | **짧은 22AWG** + JST 케이블 | 배터리 `+` 근처의 짧은 22AWG에 `SW6106 B+`와 MAX17048 JST `+`를 2갈래로 납땜 |
| 배터리 `-` 공통선 | 배터리 `-` → SW6106 `B-` | MAX17048 JST-PH 케이블 `-` | 0V | **짧은 22AWG** + JST 케이블 | 배터리 `-` 근처의 짧은 22AWG에 `SW6106 B-`와 MAX17048 JST `-`를 2갈래로 납땜 |
| 스위치 후 5V 공통선 | 스위치 긴 NO 출력 → 5V 공통선 | DFR1172 `VCC`, UWB `5V`, MAX98357A `VIN` | 5V | **짧은 22AWG** | 5V 공통선을 짧게 두 구간으로 나누고, 각 구간에 2~3개씩 직접 분기 납땜 |
| 공통 GND선 | SW6106 USB-A 2P `GND` → 공통 GND선 | DFR1172 `GND`, UWB `GND`, MAX98357A `GND` / INMP441 `GND`, BNO085 `GND`, 스위치 `LED-` | 0V | **짧은 22AWG** | GND 공통선을 짧게 두 구간으로 나누고 각 구간에 2~3개씩 직접 분기 납땜. MAX17048 `GND` 헤더에는 **별도 선을 연결하지 않음** |
| DFR1172 3.3V 공통선 | DFR1172 `3V3` → 3.3V 공통선 | INMP441 `VDD`, MAX17048 `VIN`, BNO085 `VIN` | 3.3V | 짧은 전원선 | 3.3V 공통선에서 3개 부품에 직접 분기 납땜. 5V와 절대 연결하지 않음 |
| 충전 입력 | USB 충전기 → SW6106 USB-C | 없음 | 5V 입력 | USB-C 케이블 | 충전할 때만 연결 |
| 스피커 전용선 | MAX98357A `SPK+`/`SPK-` → 8Ω 스피커 `+`/`-` | 없음 | 증폭 오디오 | 스피커선 | `SPK-`를 공통 GND에 연결하지 않음 |

**MAX17048 GND:** 멀티미터로 `SW6106 B-`와 USB-A 출력 `GND`의 도통을 먼저 확인한다. 도통이 확인되면 MAX17048 JST-PH의 `-`가 공통 GND 기준을 이미 만들므로, MAX17048 `GND` 헤더에서 공통 GND선으로 가는 중복 전선은 연결하지 않는다.

## 3. GPIO 및 통신 배정표

아래 I2C·I2S·UART 신호선은 모두 **점퍼선을 각 보드의 납땜 홀에 직접 납땜**한다. 핀헤더·듀퐁 커넥터는 사용하지 않는다.

| 장치·핀 | DFR1172 연결 핀 | 통신/주소 | 전압 | 선 | 상태 |
|---|---|---|---:|---|---|
| OV5647 FPC | `CS` MIPI-CSI 커넥터 | MIPI CSI, SCCB `GPIO7=SDA`, `GPIO8=SCL`, `0x36` | 커넥터 제공 | 동봉 FPC | **[확정]**. 일반 GPIO 배선 없음 |
| microSD | 내장 TF 슬롯 | SDIO, GPIO39–45 사용 | 내장 | 없음 | **[확정]** |
| INMP441 `SCK` | P2 `GPIO31` | I2S0 RX BCLK | 3.3V | 점퍼선 직접 납땜 | **[단위시험 필요]** |
| INMP441 `WS` | P2 `GPIO34` | I2S0 RX WS | 3.3V | 점퍼선 직접 납땜 | **[단위시험 필요]** |
| INMP441 `SD` | P2 `GPIO36` | I2S0 RX DATA | 3.3V | 점퍼선 직접 납땜 | **[단위시험 필요]** |
| INMP441 `L/R` | GND | 좌 채널 | 0V | 점퍼선 직접 납땜 | **[확정]** |
| MAX98357A `BCLK` | P2 `GPIO20` | I2S1 TX BCLK | 3.3V 신호 | 점퍼선 직접 납땜 | **[단위시험 필요]** |
| MAX98357A `LRC` | P2 `GPIO21` | I2S1 TX WS | 3.3V 신호 | 점퍼선 직접 납땜 | **[단위시험 필요]** |
| MAX98357A `DIN` | P2 `GPIO22` | I2S1 TX DATA | 3.3V 신호 | 점퍼선 직접 납땜 | **[단위시험 필요]** |
| MAX98357A `SD`/`GAIN` | 미연결 | 기본 보드 설정 사용 | - | 없음 | **[실물 확인 필요]** |
| MAX17048 `SCL` | P2 `GPIO32` | **표준 I2C1** SCL, `0x36` | 3.3V | 점퍼선 직접 납땜 | **[단위시험 필요]** |
| MAX17048 `SDA` | P2 `GPIO33` | **표준 I2C1** SDA, `0x36` | 3.3V | 점퍼선 직접 납땜 | **[단위시험 필요]** |
| MAX17048 `ALRT/INT/QStart` | 미연결 | 초기에는 폴링으로 SOC 읽기 | 3.3V | 없음 | 선택 |
| BNO085 `SDA` (센서 TX) | P2 `GPIO23` | UART1 RX, 표준 UART | 3.3V | 점퍼선 직접 납땜 | **[단위시험 필요]** |
| BNO085 `SCL` (센서 RX) | P2 `GPIO51` | UART1 TX, 표준 UART | 3.3V | 점퍼선 직접 납땜 | **[단위시험 필요]** |
| BNO085 `P1` | 3.3V(HIGH) | 표준 UART 모드 | 3.3V | 점퍼선 직접 납땜/보드 점퍼 | 실제 보드의 P0/P1 핀 또는 솔더 점퍼 확인 후 설정 **[실물 확인 필요]** |
| BNO085 `P0` | GND(LOW) | 표준 UART 모드 | 0V | 점퍼선 직접 납땜/보드 점퍼 | 실제 보드의 P0/P1 핀 또는 솔더 점퍼 확인 후 설정 **[실물 확인 필요]** |
| UWB 태그 | P4 GPIO 미연결 | 자체 Wi-Fi | 5V | 전원선만 | **[확정]** |

| 보드 내부/예약 기능 | 점유 GPIO | 외부 배정 |
|---|---|---|
| OV5647 제어 SCCB | GPIO7, GPIO8 | 카메라 전용 |
| 내장 ESP32-C6 Wi-Fi/BT | GPIO14–19, GPIO54, GPIO6 | 사용 금지 |
| 내장 PDM 마이크 | GPIO9, GPIO12 | 사용 금지 |
| 사용자 LED / BOOT | GPIO3 / GPIO35 | 사용 금지 |
| 디버그 UART | GPIO37(TX), GPIO38(RX) | 업로드·로그용 보존 |

## 4. 스위치 단자와 배선

| 스위치 뒷면 단자 | 연결 대상 | 선 | 결과 |
|---|---|---|---|
| 위·아래 긴 NO 단자 중 하나 | USB-A 2P 케이블 `+5V` | **22AWG** | 스위치 입력 |
| 다른 긴 NO 단자 | 5V 분배점 | **22AWG** | ON일 때 DFR1172·UWB·MAX98357A에 5V 공급 |
| 왼쪽 짧은 `LED+` | 5V 분배점 | 점퍼 | 시스템 ON 시 LED 점등. LED 정격 5V **[실물 확인 필요]** |
| 오른쪽 짧은 `LED-` | 공통 GND 분배점 | 점퍼 | LED GND |
| USB-A 2P 케이블 `GND` | 공통 GND 분배점 | **22AWG** | 스위치를 통과하지 않고 직결 |

## 5. 조립 전 확인사항

| 확인 항목 | 확인 방법 | 상태 |
|---|---|---|
| 배터리·SW6106 극성 | 배터리 `+/-`와 SW6106 `B+/B-`를 멀티미터로 확인 | 필수 |
| SW6106 출력 | USB-A와 2P 케이블의 `+5V/GND`, 무부하 5V 측정 | 필수 |
| GND 공통 확인 | SW6106 `B-`와 USB-A 출력 `GND`의 도통 측정 | 필수. 확인 후 MAX17048 `GND` 헤더 중복 배선 생략 |
| SW6106 충전 특성 | 충전 종료전압·충전전류·보호회로·자동출력 종료 여부 확인 | **[실물 확인 필요]** |
| 스위치 LED | LED 정격이 5V인지 확인 | **[실물 확인 필요]** |
| OV5647 | `CS` FPC 접점 방향·잠금, 카메라 `0x36` 인식 | **[단위시험 필요]** |
| MAX17048 | 표준 I2C1(GPIO32/33)에서 `0x36` 인식, 전압·SOC 읽기 | **[단위시험 필요]** |
| BNO085 | `P1=HIGH`, `P0=LOW` 표준 UART 모드 설정 후 가속도·자이로·회전벡터 동시 수신, UART 수신 버퍼 300바이트 초과 지원 확인 | **[단위시험 필요]** |
| I2S | INMP441 단독 → MAX98357A 단독 → 동시 동작 | **[단위시험 필요]** |
| 전체 전원 | 카메라·Wi-Fi·스피커 동작 중 5V 전압강하·발열 | **[단위시험 필요]** |

## 6. 조립 순서

1. 배터리·SW6106·USB-A 2P 케이블의 극성과 스위치 NO/LED 단자를 확인한다.
2. 배터리를 SW6106 `B+`/`B-`에 22AWG로 연결하고 USB-C 충전·USB-A 5V 출력을 측정한다.
3. 스위치 표대로 `+5V`만 NO 접점을 통과시키고 GND는 공통 GND 분배점으로 직결한다.
4. DFR1172 `VCC/GND`만 연결해 단독 전원 시험을 한다.
5. OV5647 → MAX17048 → INMP441 → MAX98357A → BNO085 → UWB 순서로 하나씩 연결해 시험한다.
6. 전체 연결 상태에서 전압강하·발열을 확인한다.
7. 시험이 끝난 점퍼선은 납땜+열수축 또는 잠금 커넥터로 고정한다.

## 자료

- [DFRobot DFR1172 공식 핀 안내](https://wiki.dfrobot.com/dfr1172/)
- [DFRobot DFR1172 공식 회로도 PDF](https://dfimg.dfrobot.com/wiki/21103/DFR1172_firebeetle-esp32-p4r32-development-board_schematics_V1.0.pdf)
- [ESP32-P4 표준 I2C 공식 안내](https://docs.espressif.com/projects/esp-idf/en/v5.3.6/esp32p4/api-reference/peripherals/i2c.html)
- [ESP32-P4 GPIO Matrix 공식 안내](https://docs.espressif.com/projects/esp-idf/en/latest/esp32p4/api-reference/peripherals/gpio.html)
- [OV5647 데이터시트](https://www.uctronics.com/download/Image_Sensor/OV5647_DS.pdf)
- [Adafruit MAX17048 핀 안내](https://learn.adafruit.com/adafruit-max17048-lipoly-liion-fuel-gauge-and-battery-monitor/pinouts)
- [Adafruit BNO085 보고 종류](https://learn.adafruit.com/adafruit-9-dof-orientation-imu-fusion-breakout-bno085/report-types)
