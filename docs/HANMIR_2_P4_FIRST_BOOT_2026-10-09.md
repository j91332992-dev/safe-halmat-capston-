# HANMIR 2.0 — P4 실물 초기 구동 및 서버·웹 검증

작성일: 2026-10-09. 브랜치: `feature/mobile-safety-app-20261001`.

## 1. 실제 확인한 결과

| 항목 | 확인 결과 | 확인 방법 |
|---|---|---|
| ESP32-P4 | DFR1172, 칩 rev 1.3, 16MB Flash, 32MB PSRAM | COM25 부팅 로그, PSRAM 메모리 시험 |
| 펌웨어 업로드 | ESP-IDF 5.5.5 빌드·플래시, 기록 해시 검증 성공 | esptool 로그 |
| 원본 복구 | 플래시 전체 16MB 백업 확보 | PC 로컬 백업 파일 |
| 내장 C6 통신 | P4→C6 SDIO 4비트 40MHz, Wi-Fi 접속 | SDIO 초기화 및 IP 이벤트 |
| 서버 연결 | 장치 등록·heartbeat HTTP 200, 명령·영상 WS 연결 | FastAPI 로그 |
| OV5647 | 센서 PID 0x5647, 800×640 캡처·JPEG 전송 | 보드 로그 및 웹 실제 천장 영상 |
| YOLO | 서버 `best.pt` 모델 로드·실제 추론 | 카메라 API의 `analysis.mode=real` |
| MAX17048 | SOC 약 9% 읽힘 | heartbeat 배터리 값. 정확도·충방전 추적은 별도 검증 |
| 스피커 | 웹 명령 전달 및 WAV 재생 완료 보고 | `last_speaker_status=ok`. 사람이 듣는 음질은 별도 확인 |
| 마이크 처리 | INMP441 I2S·AFE VAD·독립 WebRTC NS 초기화 | 보드 로그. 실제 음성 녹음·인식률 검증은 미완료 |
| OpenAI | API 인증·설정 모델 접근 및 합성 음성 STT/설명 응답 성공 | 로컬 환경에서 API 호출 |
| 웹 | 실시간 연결 복구·P4 영상·배터리 규칙 응답 | 브라우저 확인 |
| 서버 회귀 시험 | 77개 통과 | `pytest tests -q` |
| 웹 빌드 | TypeScript 및 Vite production 빌드 성공 | tsc·Vite 로그 |

**전 기능 완료를 뜻하지 않는다.** 아직 사람을 향한 PPE 정확도, 실제 마이크 호출 성공률, 긴급 음성 종단 전달 시간, 양방향 통화, BNO085 방향·낙상 판정은 확인하지 않았다. UWB 태그는 독립 장치이며 이번 연결에서 오프라인이다.

최종 업로드된 버전은 `2.0.0-p4-hw-bringup-20261009`이다. heartbeat에서 camera=capturing, battery=ready, speaker=initialized, mic=initialized, noise_suppression=ready를 확인했다. **마이크 PCM peak는 1/32768이고 실제 음성 업로드는 아직 없다.** 초기화는 됐지만 유효 음성 입력을 확인하지 못했다. 발화 중에도 같은 값이면 INMP441 3.3V·GND·L/R=GND·BCLK31·WS34·SD36 배선과 채널을 확인한다.

## 2. 이번에 수정한 펌웨어

- 칩 rev 1.3에 필요한 `ESP32P4_SELECTS_REV_LESS_V3` 설정. rev 3 기본 이미지와 혼용하지 않는다.
- DFR1172의 내장 C6 SDIO 핀: CLK18, CMD19, D0–D3=14–17, RESET54. 제조사 자료를 기준으로 설정.
- OV5647 캡처 빈 함수를 V4L2 MIPI CSI·ISP RGB565·하드웨어 JPEG 경로로 구현.
- 초기 영상 설정은 800×640, JPEG 품질 75, 캡처 목표 최대 10 FPS. 카메라 센서 내부 모드 50 FPS와 서버 수신·추론 FPS는 서로 다르다.
- 최신 프레임 1장 큐와 기존 HMR2 바이너리 WS 전송을 연결. 오래된 프레임은 버리므로 프레임 드롭 수 자체가 전송 실패 횟수를 뜻하지 않는다.
- AFE에 `WEBRTC`를 NS 모델 이름으로 넣던 설정은 런타임 초기화에 실패했다. `esp_ns.h`의 WebRTC NS를 독립 10ms 프레임으로 처리한 뒤 AFE VAD로 전달하도록 수정.
- AFE 프레임 512샘플과 NS 프레임 160샘플 크기가 달라 버퍼로 연결. NS 초기화 상태와 마이크 PCM peak 로그를 추가.
- heartbeat에 카메라 캡처·마이크·NS·스피커·배터리·IMU의 실제 초기화 상태를 반영하도록 수정. 초기화 성공은 음질이나 인식률 평가 성공과 다르다.
- `sdkconfig.dfr1172.example`에 연결한 외부 부품 핀과 카메라 센서 선택을 제공. Wi-Fi 비밀번호와 토큰은 포함하지 않는다.
- `dependencies.lock`에 이번 컴포넌트 버전을 기록. ESP-Hosted 3.0.9, Wi-Fi Remote 1.6.5, ESP-SR 2.5.5, ESP-Video 2.5.0, ESP-Cam-Sensor 2.6.0.

### 확인 과정에서 해결한 문제

1. Wi-Fi SSID `WISET`로는 AP를 찾지 못했다. PC의 실제 스캔 결과 `WISET_2.4G`를 적용해 접속했다.
2. 첫 카메라 초기화는 센서 ID 읽기가 실패했다. 사용자가 카메라 연결을 확인한 뒤 재부팅에서 PID 및 영상 캡처가 성공했다.
3. AFE NS 모델 초기화 실패를 독립 WebRTC NS 경로로 수정했다.
4. C6는 출고 버전을 `0.0.0`으로 보고하여 호스트와 버전 불일치 로그가 있다. 실제 SDIO·Wi-Fi·WS 통신은 동작했으며 C6를 별도 플래시하지 않았다. 장시간 부하·재접속은 추가 시험한다.

## 3. 현재 AI Agent와 수정 내용

### 모델과 처리 위치

- STT: 서버 OpenAI `gpt-4o-mini-transcribe`.
- 설명형 응답: 서버 OpenAI `gpt-6-luna`, reasoning none, 짧은 출력·호출 시간 제한.
- TTS: 서버 Edge TTS 한국어 음성 → 16kHz·16bit·mono WAV → P4 I2S 스피커.
- P4 로컬: 마이크 입력, WebRTC NS, VAD, 300ms pre-roll, 최대 5초 WAV 구간, 업로드, 명령 수신·재생.
- 서버 로컬: 호출어 게이트, intent 분류, 상태·배터리·위치·PPE 답변, 위험 규칙, 대피 계산, 긴급 처리.

### 답변 로직

1. 긴급어·신체 위험 표현을 일반 상태 질문·관리자 연결보다 먼저 판정한다.
2. 배터리·PPE·장치 상태·방향 질문 intent를 추가하고 단순 조회에서 LLM을 호출하지 않는다.
3. 위치는 최근 UWB 수신, PPE·영상 상태는 최근 카메라 수신, 배터리는 최근 장치 heartbeat를 근거로 한다.
4. 최신 정보가 없으면 과거 DB 값으로 현재 상태를 확정하거나 안전한 작업 지속을 권하지 않고 ‘확인 불가’로 답한다.
5. 설명형 AI에도 최신 정보가 없는 센서 값은 ‘확인 불가’로 전달한다.
6. BNO085 방향 데이터가 구현·검증되지 않아 방향 질문은 확인 불가로 응답한다.

### 호출어·긴급어의 현재 한계

‘투투스’ 전용 WakeNet과 로컬 긴급어 모델은 아직 없다. 현재는 **소음 제거 → VAD 녹음 → 서버 STT → 호출어/긴급어 판정**이다. ‘살려주세요’, ‘화재발생’, ‘불이야’ 등은 서버 게이트에서 호출어 없이 통과하지만, 네트워크·STT가 실패하면 로컬에서 긴급 신고를 확정할 수 없다. 스피커 재생 중에는 마이크 구간을 버리므로 재생 중 비상어 감지는 현재 지원하지 않는다.

사용자가 기억하는 60~70% 성공률은 기준 측정치가 아니다. 이번 초기화·합성 음성 API 확인만으로 향상률을 주장할 수 없다. 같은 화자·거리·소음·문구의 반복 실험에서 미탐·오탐·P50/P95 지연을 측정해야 한다.

합성 음성 단일 연결 시험: TTS 약 3.3초, STT 약 7.0초, 설명 생성 약 3.7초. 캐시·네트워크·PC 부하의 영향을 받으며 실제 마이크 호출의 종단 지연이나 정상 성능 목표를 뜻하지 않는다.

## 4. 웹 수정

- React 개발 모드 effect 정리 시 WebSocket 연결 중 상태가 남아 재접속을 막던 문제를 수정. 정리 시 연결 플래그·소켓·이벤트 핸들러를 초기화.
- Vite의 `/tts` 프록시 추가.
- 서버와 웹을 실제 hardware 모드로 시작. 웹에서 장치 1/2 연결 및 실시간 카메라 원본 수신을 확인.

## 5. PC 실행 환경과 재현

- 저장소: `C:\Users\조성준\OneDrive - pukyong.ac.kr\바탕 화면\hanmmir2.0`
- IDF: `C:\Espressif\frameworks\esp-idf-v5.5.5`
- IDF Python: `C:\Espressif\python_env\idf5.5_py3.12_env`
- ASCII 빌드 경로: `C:\dev\hanmir-p4\helmet_p4`
- 장치 포트: COM25. USB 재연결 시 바뀔 수 있다.
- 웹: `http://localhost:5173`, 서버: `http://localhost:8000`.
- 현재 LAN: 서버 PC `192.168.0.40`, P4 `192.168.0.43`. DHCP 주소는 재확인한다.
- 원본 백업: `C:\dev\hanmir-runtime\p4-original-flash.bin`.
- 로그·웹 캡처: `C:\dev\hanmir-runtime`.

빌드는 공식 IDF 환경을 초기화한 PowerShell에서 `idf.py set-target esp32p4`, `idf.py menuconfig`, `idf.py build`, `idf.py -p COM25 flash` 순서로 진행한다. 한글·공백이 있는 저장소 경로 대신 ASCII 작업 경로를 사용했다. 보드 설정 예제를 defaults와 함께 적용하되 SSID·서버주소·카메라 토큰은 사용 장소의 로컬 설정에 입력한다.

서버는 루트 `.venv` Python으로 backend 디렉터리에서 `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`, 웹은 frontend에서 `npm run dev -- --host 0.0.0.0 --port 5173`으로 시작한다. 서버 `backend/.env`의 카메라 토큰과 P4 설정을 일치시킨다.

API 키·비밀번호·카메라 토큰·로컬 sdkconfig·백업 이미지·설정이 포함된 펌웨어 바이너리는 Git에 올리지 않는다. 새 PC에서는 별도로 설정해야 한다.

## 6. 이어서 할 실물 시험

1. 마이크 가까이서 ‘투투스 배터리 얼마야’를 말하고 PCM peak, WAV 업로드, STT 텍스트, intent, 스피커 완료 로그를 대조.
2. 실제 스피커 청취 확인. 소리·음량·잡음·재생 중 마이크 중단 동작 확인.
3. 테스트 환경에서 ‘살려주세요’, ‘불이야’를 호출어 없이 시험. 긴급 이벤트·관제 표시·응답 시간을 확인하고 시험 경보를 정리.
4. 사람과 보호구가 보이는 장면에서 원본/분석 영상을 비교. 이번 천장 장면만으로 PPE 인식률을 평가하지 않는다.
5. 빌드를 멈춘 PC에서 영상 수신 FPS·YOLO 분석 FPS·지연·드롭을 각각 측정. 현재 YOLO는 CPU로 동작한다.
6. BNO085 모드·UART baud·SHTP 보고 검증 후 방향·낙상 기능 구현. 현재 펌웨어는 낙상·방향을 보고하지 않는다.
7. 양방향 통화 PCM, 오프라인 긴급 전달 보존, 맞춤 WakeNet·긴급어 모델, AEC는 별도 작업으로 남아 있다.

## 7. 기준 자료

- [DFRobot 보드·SDIO 핀 자료](https://wiki.dfrobot.com/dfr1172/)
- [Espressif 공식 영상 예제](https://github.com/espressif/esp-video-components/tree/master/esp_video/examples/capture_stream)
- 저장소의 2026-10-01 최종 HW 배선 및 기존 HANMIR 서버·S3 코드.
