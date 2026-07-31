# 하드웨어 A to Z 가이드

이 문서는 안전모 AV 장치, UWB 태그, UWB 앵커 4개와 전원부를 실제로 제작하고 최종 통합 프로그램에 연결하는 전체 절차입니다. 부품별 일회용 테스트 스케치는 만들지 않습니다. 확인은 최종 펌웨어의 시리얼 로그, 서버 API와 관리자 웹의 하드웨어 진단 화면으로 수행합니다.

## 1. 담당 파트

| 파트 | 담당 범위 | 주요 파일 | 완료 기준 |
|---|---|---|---|
| AV 하드웨어 | OV5640, INMP441, MAX98357A, 스피커, 버튼 | `firmware/helmet_av_device/src/config.h`, `camera_manager.cpp`, `audio_recorder.cpp`, `speaker_manager.cpp`, `button_manager.cpp` | 관리자 웹에서 카메라·음성·버튼·스피커 상태와 최근 수신 시간이 확인됨 |
| UWB 하드웨어 | 안전모 태그, 앵커 4개, 거리 측정 | `firmware/uwb_position_device/src/config.h`, `uwb_dw3000_adapter.cpp`, `firmware/uwb_anchor/` | 앵커별 거리 3개 이상이 서버로 전송되고 지도 위치가 갱신됨 |
| 전원·기구 | LiPo, TP4056, TPS61088, 스위치, 절연·장착 | 이 문서와 `config.h` | 부하 상태 5V 유지, 쇼트·과열 없음, 안전모 무게 균형 확보 |
| 통합 진단 | Wi-Fi, 장치 ID, heartbeat, WebSocket 명령 | `server_client.cpp`, `websocket_client.cpp`, 관리자 진단 화면 | 두 ESP32 online, battery/RSSI/component status 갱신 |

## 2. 절대 안전 원칙

- 모든 착용형 부품은 안전모에 넣습니다. 조끼나 허리에 배터리·보드·센서를 분산하지 않습니다.
- 안전모 충격 흡수재를 자르거나 구멍을 뚫지 않습니다. 비구조용 브래킷, 벨크로와 절연 케이스를 사용합니다.
- 3.7V LiPo를 ESP32 5V 핀에 직접 연결하지 않습니다. 7.4V 이상도 직접 연결하지 않습니다.
- INMP441에는 3.3V만 공급합니다.
- 스피커는 반드시 MAX98357A의 `SPK+`, `SPK-`에 연결합니다. ESP32 GPIO에 직접 연결하지 않습니다.
- 모든 신호 장치는 공통 GND를 사용합니다.
- 배터리 팽창, 냄새, 심한 발열, 피복 손상이 있으면 즉시 전원을 분리합니다.
- 실제 산업 현장 사용 전 보호구 인증과 전기·배터리·무선 안전 검토가 필요합니다.

## 3. 준비물

안전모 내부: ESP32-S3-CAM+OV5640, 160° 카메라 모듈, INMP441, MAX98357A, 8Ω 스피커 2개, 순간 누름 버튼, ESP32 UWB DW3000 태그, 3.7V 5000mAh LiPo, 예비 2000mAh LiPo, TP4056 보호형 충전 모듈, TPS61088, 스위치, 커넥터, 전선, 절연 시트, 수축튜브, 벨크로.

현장: UWB DW3000 앵커 4개, 앵커별 5V USB 전원과 케이블, 고정재, 줄자.

공구: 멀티미터, 납땜 인두, 와이어 스트리퍼, 절연 공구, 라벨, 데이터 USB 케이블, 노트북.

## 4. 제작 전 보드 확인

1. 각 보드의 정확한 제품명과 리비전, 판매처 핀맵과 회로도를 저장합니다.
2. ESP32-S3-CAM의 카메라·PSRAM·USB/JTAG 사용 핀을 표로 만듭니다.
3. UWB 보드가 DW3000을 내장 연결했는지, 외장 SPI 연결이 필요한지 확인합니다.
4. 추천 핀과 충돌하는 GPIO를 찾고 `config.h`에서만 수정합니다.
5. AV 장치 ID는 `helmet-001-av`, 위치 장치는 `helmet-001-uwb`, 태그는 `tag-001`로 맞춥니다.

## 5. 전원부 제작

### 5.1 LiPo와 TP4056

1. 배터리를 회로에서 분리하고 멀티미터로 실제 극성을 확인합니다.
2. 배터리 양극을 TP4056 `B+`, 음극을 `B-`에 연결합니다.
3. 보호형 TP4056의 부하 출력 `OUT+`, `OUT-`을 사용합니다.
4. 노출된 납땜부를 수축튜브와 절연판으로 덮습니다.
5. 충전 USB를 연결하고 충전 LED, 온도, 배터리 상태를 확인합니다.

### 5.2 TPS61088과 스위치

1. TP4056 `OUT+`→전원 스위치→TPS61088 `VIN+` 순서로 연결합니다.
2. TP4056 `OUT-`→TPS61088 `GND`를 연결합니다.
3. ESP32와 앰프는 아직 연결하지 않습니다.
4. 전원을 켜고 TPS61088 출력과 GND를 멀티미터로 측정합니다.
5. 가변저항을 천천히 조절해 무부하 출력 5.0V로 맞춥니다.
6. 전원을 여러 번 껐다 켜도 4.9~5.1V 범위인지 확인합니다.
7. 출력 5V를 ESP32 5V/VIN과 MAX98357A VIN으로 분기하고 GND는 공통 버스로 만듭니다.

배터리 전압을 ADC로 읽을 때는 분압기를 거쳐야 합니다. 배터리를 ADC에 직접 연결하지 않습니다.

## 6. AV 장치 핀 연결

아래 GPIO는 추천 시작값일 뿐입니다. 실제 카메라 회로도와 겹치면 주변기기 핀을 변경합니다.

| 부품 | 부품 핀 | ESP32 연결 | config 이름 | 주의 |
|---|---|---:|---|---|
| INMP441 | VCC | 3.3V | - | 5V 금지 |
| INMP441 | GND | 공통 GND | - | 필수 |
| INMP441 | SCK/BCLK | GPIO4 | `I2S_MIC_BCLK` | 충돌 확인 |
| INMP441 | WS/LRCL | GPIO5 | `I2S_MIC_WS` | 충돌 확인 |
| INMP441 | SD | GPIO6 | `I2S_MIC_DATA` | ESP32 입력 |
| INMP441 | L/R | GND | - | 왼쪽 채널 |
| MAX98357A | VIN | 안정화 5V | - | TPS61088 출력 |
| MAX98357A | GND | 공통 GND | - | 필수 |
| MAX98357A | BCLK | GPIO15 | `I2S_SPK_BCLK` | 충돌 확인 |
| MAX98357A | LRC/WS | GPIO16 | `I2S_SPK_WS` | 충돌 확인 |
| MAX98357A | DIN | GPIO17 | `I2S_SPK_DATA` | ESP32 출력 |
| MAX98357A | SPK+/SPK- | 8Ω 스피커 | - | SPK-는 GND가 아님 |
| 버튼 | 한쪽 | GND | - | 누르면 LOW |
| 버튼 | 다른 쪽 | GPIO18 | `BUTTON_PIN` | `INPUT_PULLUP` |
| 배터리 분압 출력 | ADC | GPIO7 | `BATTERY_ADC_PIN` | 분압 필수 |

OV5640의 D0~D7, XCLK, PCLK, VSYNC, HREF, SIOD, SIOC, PWDN, RESET은 보드 회로도 값만 사용합니다. 현재 `CAMERA_PIN_*=-1`, `ENABLE_CAMERA_HARDWARE=false`이므로 확인한 값을 모두 입력한 뒤 `true`로 바꿉니다.

## 7. 카메라 제작과 확인

1. 전원을 끄고 FPC 커넥터 잠금 레버를 엽니다.
2. 접점 방향을 회로도와 대조한 뒤 케이블을 수평으로 끝까지 넣고 잠급니다.
3. 외장 점퍼 방식이면 모든 데이터/클럭/SCCB 신호를 제조사 핀맵 그대로 연결합니다.
4. 렌즈가 안전모 챙과 케이블에 가리지 않도록 전면 상단에 고정합니다.
5. 최종 AV 펌웨어를 업로드합니다.
6. 시리얼에서 `[CAMERA] 초기화 성공`, 서버에서 `/api/camera/frame` 2xx, 웹에서 마지막 카메라 수신 시간을 확인합니다.

## 8. 마이크 제작과 확인

1. 전원을 끄고 INMP441 VCC→3.3V, GND→공통 GND를 연결합니다.
2. SCK→`I2S_MIC_BCLK`, WS→`I2S_MIC_WS`, SD→`I2S_MIC_DATA`를 연결합니다.
3. L/R은 GND에 연결해 왼쪽 채널로 맞춥니다.
4. 신호선을 앰프/승압기 전원선과 길게 평행 배선하지 않습니다.
5. 마이크 구멍을 막지 않고 턱끈 근처에 고정합니다.
6. 최종 펌웨어에서 16kHz mono 16bit PCM, 3~5초 녹음을 사용합니다.
7. `[AUDIO]` 초기화·레벨·업로드 로그와 웹의 마지막 음성 수신 시간을 확인합니다.

## 9. 스피커 제작과 확인

1. MAX98357A VIN→5V, GND→공통 GND를 연결합니다.
2. BCLK/LRC/DIN을 각각 `I2S_SPK_*` 핀에 연결합니다.
3. 스피커 한 개를 `SPK+`, `SPK-` 사이에 연결합니다.
4. 스피커 두 개의 병렬 연결은 4Ω이 될 수 있으므로 앰프 허용 임피던스를 확인합니다. 안전한 시작은 직렬 연결 또는 앰프 추가입니다.
5. 관리자 웹에서 `안전모에 경고 보내기`를 누릅니다.
6. 서버 command→장치 WebSocket→`[SPEAKER]` 출력→다음 heartbeat 상태 순서로 확인합니다.

## 10. 비상 버튼 제작과 확인

1. 버튼 한쪽은 GND, 다른 쪽은 `BUTTON_PIN`에 연결합니다.
2. 평상시 HIGH, 누르면 LOW인지 확인합니다.
3. 기본값은 debounce 40ms, 다중 클릭 450ms, long press 1200ms입니다.
4. single=음성 녹음, double=상태 보고, triple=즉시 비상, long=관리자 호출입니다.
5. 장갑을 낀 손으로 누르기 쉬운 안전모 측면에 고정합니다.
6. 최종 웹 이벤트 로그와 위험도 변화로 확인합니다.

## 11. UWB 태그와 앵커 핀

| DW3000 신호 | 추천 GPIO | config 이름 |
|---|---:|---|
| SCK | 18 | `UWB_SPI_SCK` |
| MISO | 19 | `UWB_SPI_MISO` |
| MOSI | 23 | `UWB_SPI_MOSI` |
| CS | 5 | `UWB_SPI_CS` |
| IRQ | 34 | `UWB_IRQ` |
| RST | 27 | `UWB_RST` |

내장형 UWB 개발보드는 제조사 고정 핀을 우선합니다. 태그는 앵커별 거리와 품질만 서버로 전송하며 x,y를 계산하지 않습니다.

## 12. UWB 앵커 4개 설치

1. 각 앵커 펌웨어의 `ANCHOR_ID`를 `anchor-001`~`anchor-004`로 다르게 설정합니다.
2. 각 보드에 규격에 맞는 5V USB 전원을 공급하고 전원 LED와 시리얼 ID를 확인합니다.
3. 현장 왼쪽 아래를 (0,0), 긴 방향을 +x, 수직 방향을 +y로 정합니다.
4. 앵커를 넓은 사각형 모서리의 높은 고정 지점에 설치합니다. 일직선 배치를 피합니다.
5. 줄자로 앵커 안테나 중심의 x,y,z를 미터 단위로 측정합니다.
6. 기본 예시는 (0,0), (12,0), (12,8), (0,8), z=2.2m입니다.
7. `/api/anchors` 또는 관리자 기능으로 실제 좌표를 등록합니다.

## 13. 실제 DW3000 전환

1. 처음에는 `UWB_USE_MOCK=true`로 서버와 웹 계약을 확인합니다.
2. 정확한 보드와 DW3000 라이브러리 버전을 확정합니다.
3. `uwb_dw3000_adapter.cpp` 안에서만 TWR ranging을 구현합니다.
4. `IUwbTag` 인터페이스와 `/api/uwb/distances` JSON 필드는 바꾸지 않습니다.
5. 실제 거리와 측정 거리를 앵커별로 기록하고 offset과 quality를 보정합니다.
6. 완료 후 `UWB_USE_MOCK=false`로 바꿉니다.

## 14. 안전모 내부 장착

- 카메라: 전면 상단, 수평 유지
- ESP32-S3-CAM: 카메라 근처 절연 케이스
- 마이크: 입 방향 측면/턱끈 근처
- 스피커: 귀를 완전히 막지 않는 측면
- 버튼: 장갑 낀 손으로 누르기 쉬운 바깥 측면
- UWB 태그: 상단 또는 후면 상단, 금속·스피커 자석과 떨어진 곳
- 배터리: 후면 중앙, 무게 균형과 완충 고려
- TP4056/TPS61088: 배터리 근처 절연·통풍 케이스
- 케이블: 목과 얼굴에 닿지 않게 고정하고 커넥터 앞에 장력 완화

장착 후 시야 가림, 흔들림, 날카로운 모서리, 턱끈 간섭, 발열을 확인합니다.

## 15. PlatformIO 업로드

1. VS Code와 PlatformIO IDE를 설치합니다.
2. 세 펌웨어 폴더를 각각 PlatformIO 프로젝트로 엽니다.
3. 정확한 board ID, COM 포트, 데이터 USB 케이블을 확인합니다.
4. `config.h`의 Wi-Fi, PC IPv4, 핀, 장치 ID를 수정합니다.
5. Build→Upload→Monitor 115200 순서로 실행합니다.
6. 자동 부트가 실패하면 보드 매뉴얼에 따라 BOOT/RESET을 사용합니다.

정상 로그의 핵심은 `[WIFI] 연결 성공`, `[SERVER] 장치 등록 성공`, `[HEARTBEAT] 성공`, 각 부품 초기화·수신·전송 성공입니다.

## 16. 최종 통합 확인

1. PC에서 `run_all.bat`을 실행합니다.
2. AV 장치와 위치 태그가 관리자 진단에서 online인지 확인합니다.
3. heartbeat, RSSI, battery가 5초 간격으로 갱신되는지 봅니다.
4. 카메라→음성→버튼→스피커→UWB 순으로 작동시킵니다.
5. 위험구역 안으로 천천히 이동해 3회 연속 판정 후 이벤트와 위험도 +30을 확인합니다.
6. 전원을 10분 이상 유지하며 승압기·앰프·배터리 발열과 재연결을 확인합니다.

## 17. 문제별 담당 파일

| 증상 | 물리 확인 | 수정 파일 |
|---|---|---|
| 전원 리셋 | 부하 순간 5V, 쇼트, 선 굵기 | 전원부/배선, `battery_manager.cpp` |
| 카메라 실패 | FPC, 핀, PSRAM, 전압 | AV `config.h`, `camera_manager.cpp` |
| 마이크 무음 | 3.3V, L/R, BCLK/WS/SD | `audio_recorder.cpp` |
| 스피커 무음 | 앰프 5V, SPK+/-, I2S | `speaker_manager.cpp`, `websocket_client.cpp` |
| 버튼 오류 | GND, HIGH/LOW, 접점 | `button_manager.cpp` |
| UWB 거리 없음 | 앵커 ID/전원, SPI/IRQ/RST | UWB `config.h`, `uwb_dw3000_adapter.cpp` |
| 서버 연결 실패 | 2.4GHz, PC IP, 방화벽 8000 | `wifi_manager.cpp`, `server_client.cpp` |

AI에게 수정 요청할 때 정확한 보드/리비전, 실제 핀, PlatformIO/Arduino Core 버전, 전체 시리얼 로그, 서버 HTTP 오류, 진단 JSON, 측정한 5V/3.3V를 함께 제공합니다.
