# HANMIR 2.0 ESP32-P4 통합 펌웨어 — 실물 초기 구동

갱신일: 2026-10-09. DFR1172 ESP32-P4 rev 1.3에서 ESP-IDF 5.5.5 빌드·플래시, 내장 C6 SDIO Wi-Fi, 서버 등록, OV5647 800×640 JPEG 영상의 웹 수신, MAX17048 SOC 읽기를 확인했다. 기존 S3와 음성 실험 프로젝트는 유지한다. 마이크 인식률·청취 품질, BNO085, 양방향 통화는 별도 실물 검증이 필요하다.

## 구현된 경로

| 모듈 | 상태 | 코드 |
|---|---|---|
| 내장 C6 Wi-Fi | ESP-Hosted + `esp_wifi` STA 시작·IP 이벤트·재연결 | `network.c` |
| 서버 상태 | 기존 등록/heartbeat API, 끊김 뒤 재등록, RSSI·구성품 상태 | `api_client.c` |
| 영상 전송 | JPEG 원본 최신 1장 큐, P4용 `HMR2` 바이너리 WebSocket, 끊김 후 라이브러리 재연결 | `camera_transport.c` |
| 영상 기준선 | 메뉴에서 기존 multipart POST를 선택해 S3/P4 동일 서버 경로 비교 | `camera_transport.c` |
| 명령 수신 | 기존 `/ws/device/{id}` 별도 채널, 톤·경보·TTS WAV 재생 | `command_client.c`, `speaker.c` |
| 음성 입력 | INMP441 I2S 16kHz, ESP-SR WebRTC NS/VAD, 300ms 앞부분 보존, 최대 5초 WAV 업로드 | `voice.c` |
| 배터리 | MAX17048 표준 I2C1 SOC 폴링, 유효 값만 heartbeat 전송 | `sensors.c` |
| GPIO 점검 | 최종 배선표의 보드 예약 핀 및 외부 장치 간 중복 할당 시 시작 거부 | `pin_guard.c` |
| UWB | 독립 Wi-Fi 태그. P4 연결선과 코드 없음 | 기존 펌웨어·백엔드 유지 |

## 아직 하드웨어 검증 없이는 완료할 수 없는 경로

- `camera_source.c`에 OV5647 **MIPI CSI → ISP RGB565 → 하드웨어 JPEG** 캡처가 구현됐다. 기본 설정은 카메라 비활성이며 `sdkconfig.dfr1172.example`에 실제 연결한 보드용 활성화 설정을 제공한다. 초기 목표는 800×640, JPEG 품질 75, 최대 10 FPS이다. 실효 수신 FPS와 YOLO 정확도는 장면·네트워크·CPU 추론에 따라 별도로 측정한다.
- `투투스` 맞춤 WakeNet 모델과 비상어 모델은 아직 확보·평가하지 않았다. 따라서 현재 음성은 **VAD 구간을 서버에 보내 기존 STT 호출어/긴급어 게이트가 판정**한다. WakeNet 히트를 긴급 신고로 취급하지 않는다. 기본 설정에서 음성은 꺼져 있고 실물 핀 확인 뒤 켠다.
- 통화의 양방향 PCM, 버튼, BNO085 SHTP 낙상 판정, microSD 로그, AEC playback reference는 연결 전 실제 드라이버·지연 시험이 필요하다. 서버가 보낸 해당 명령을 현재 펌웨어가 수행한다고 가정하면 안 된다.
- 일반 음성 클립은 메모리 큐 3개와 3회 업로드 시도만 있다. 전원 차단 시 오프라인 영속성이 없으므로 긴급 신고 전달 보장을 주장하지 않는다.
- HTTP와 WS는 현장 LAN의 `http://`/`ws://` 기준이다. 원격망 배포 전 TLS·장치별 인증을 설계해야 한다. 영상 WS는 별도 토큰이 있어야 연결된다.

## 연결 전 설정

1. Espressif ESP-IDF **5.5 이상**과 컴포넌트 관리자 환경을 준비한다. ESP-Hosted MCU 최신 Wi-Fi 예제는 P4에서 `esp_wifi_remote` 경로를 사용한다. DFR1172 내장 C6의 출고 펌웨어와 ESP-Hosted 호스트 버전이 맞는지 확인하고, 제조사 절차 없이 C6를 임의로 재플래시하지 않는다.
2. `idf.py set-target esp32p4`, `idf.py menuconfig`를 실행한다. **HANMIR P4 integration** 메뉴의 SSID, Wi-Fi 비밀번호, 서버 PC LAN IP/포트, ID, 카메라 토큰을 입력한다. 토큰은 서버 `backend/.env`의 `CAMERA_INGEST_TOKEN`과 같게 한다. 토큰은 URL이 아닌 WebSocket 헤더로 전송된다.
3. MAX17048는 실물 확인 뒤 SDA=33, SCL=32를 메뉴에 입력한다. INMP441은 BCLK=31, WS=34, DATA=36, MAX98357A는 BCLK=20, WS=21, DIN=22가 최종 배선표의 **단위시험 후보**다. 기본 `-1`은 비활성이다. 확인 전 숫자를 넣지 않는다.
4. 이번 보드는 rev 1.3이므로 `CONFIG_ESP32P4_SELECTS_REV_LESS_V3=y`가 필요하다. 16MB Flash·32MB PSRAM을 부팅 로그로 확인했다. C6 SDIO 핀은 제조사 자료의 CLK18/CMD19/D0–D3=14–17/RESET54이며 기본 설정에 반영했다. 비밀번호·카메라 토큰이 들어가는 로컬 `sdkconfig`와 빌드 바이너리는 공유하지 않는다.
5. 서버는 기존 `backend`로 시작한다. `/api/devices/register`, `/api/devices/heartbeat`, `/ws/device/{id}`, `/api/audio/upload`는 기존 경로다. `HANMIR_CAMERA_HTTP_BASELINE`을 켜면 S3와 같은 `/api/camera/frame`으로 기준선을 얻는다. 끄면 새 영상 `/api/camera/stream/{device_id}`를 사용한다.

## 권장 실물 시험 순서

1. P4 USB 로그·NVS·C6 Wi-Fi 연결과 서버 등록/heartbeat. 재부팅·AP 차단·서버 재시작 뒤 복구 확인.
2. MAX17048 I2C1 `0x36`을 카메라 SCCB `0x36`과 **별도 버스**에서 확인. 배터리 SOC 값이 heartbeat에 나타나는지 확인.
3. INMP441 단독 I2S → NS/VAD → 서버 WAV 수신·STT. 조용한 현장과 소음 현장에서 `투투스`, 긴급 문구의 미탐·오탐·지연 측정.
4. MAX98357A 단독 톤과 TTS WAV. 스피커 음성이 마이크로 재인식되지 않는지 확인. 이후 AEC 기준 PCM 연결을 평가.
5. 카메라 원본·ISP·JPEG는 초기 연결 확인을 마쳤다. 사람을 향한 장면에서 노출·색상·초점·움직임 품질을 확인한 뒤 YOLO 임계값과 해상도를 조정한다. 센서 ID 오류가 나면 전원을 끄고 CSI FPC 삽입 방향·잠금을 먼저 확인한다.
6. 프레임 전송 서버 ACK, 원본 미리보기, YOLO 분석 화면을 순차 확인. 카메라 단독·음성 동시·UWB 동시 조건에서 수신 FPS, 분석 FPS, 지연, 드롭을 따로 측정.
7. 비상어 전달, 서버 다운·AP 다운·전원 재부팅 시나리오. 오프라인 영속성이 필요하면 전원·microSD 검증 후 추가.

## P4 영상 패킷 v1

한 WebSocket **binary message**에 16바이트 헤더와 JPEG를 넣는다. 헤더는 ASCII `HMR2` 4바이트, big endian `frame_id` uint64, `width` uint16, `height` uint16이다. 서버는 JPEG SOI/EOI, 크기, 프레임 번호 증가, 장치·작업자 매핑을 검사한다. 일반 프레임은 오래된 대기 프레임을 버린다. 서버는 첫 프레임과 8프레임마다 `frame_ack` JSON으로 프레임 번호·분석 큐 깊이를 전송한다. 음성/명령은 이 소켓과 별도로 처리한다.

## 사용한 기준

- [DFRobot DFR1172 보드 자료](https://wiki.dfrobot.com/dfr1172/)
- [ESP-Hosted MCU Wi-Fi STA 예제](https://github.com/espressif/esp-hosted-mcu/blob/main/examples/wifi/sta/README.md)
- [ESP-Video Components 시작 안내](https://docs.espressif.com/projects/esp-video-components/en/latest/esp32p4/Get_Started/index.html)
- [프로젝트 배선표](../../docs/HARDWARE_REDESIGN_ESP32P4.md), [통신 개편 계획](../../docs/HANMIR_2_P4_COMMUNICATION_PLAN_2026-10-02.md)
