# 한미르 통합최종본

위치/UWB·지도 설계, 음성·AI 어시스턴트, ESP32-S3 카메라·YOLO를 하나의 시스템으로 통합한 최종 테스트 버전입니다.

처음 실행할 때는 [통합_시작가이드.md](통합_시작가이드.md)를 먼저 따라 하세요. 구체적인 병합·수정·검증 결과는 [INTEGRATION_SUMMARY.md](INTEGRATION_SUMMARY.md)에 정리되어 있습니다.

---
# ESP32 스마트 안전모 실시간 안전관제 시스템

ESP32-S3-CAM 기반 AV 장치와 ESP32 UWB DW3000 위치 장치가 데이터를 수집하고, Windows PC의 FastAPI 서버가 영상·음성·위치·위험도를 통합하며, React 관리자 웹이 이를 실시간으로 보여주는 1차 통합 프로그램입니다.

이 저장소는 부품별 일회용 테스트 스케치를 모은 프로젝트가 아닙니다. 카메라, 마이크, 스피커, 버튼, UWB, 서버, 지도, 위험도, 이벤트와 하드웨어 진단을 처음부터 하나의 최종 구조로 실행합니다. 부품 확인은 각 펌웨어의 시리얼 로그, heartbeat API, 서버 로그와 관리자 웹의 `하드웨어 진단` 화면을 이용합니다.

## 빠른 실행(Windows)

필수 준비: Python 3.11 이상, Node.js 20 이상, npm.

```bat
install_windows.bat
run_all.bat
```

그다음 브라우저에서 `http://localhost:5173`을 엽니다. API 문서는 `http://localhost:8000/docs`입니다. 처음에는 `mock` 모드이며, 지도 위 작업자와 UWB 앵커 4개, 위험구역, 위험도, 이벤트와 장치 상태가 표시됩니다.

개별 실행:

```bat
run_backend.bat
run_frontend.bat
run_simulator.bat
```

## 실제 UWB 위치지도 실행

TAG와 Anchor 4개 펌웨어 입력 및 배치가 끝난 뒤, TAG 시리얼 모니터를 `Ctrl+C`로 종료하고 다음을 실행합니다. 이 실행 방식은 mock 시뮬레이터를 켜지 않습니다.

```bat
run_hardware_map.bat COM6
```

세 개의 창(백엔드, 프런트엔드, UWB 연결기)이 열리면 `http://localhost:5173`에서 실시간 위치를 확인합니다. TAG의 COM 번호가 바뀌면 `COM6` 대신 현재 번호를 사용합니다. 중앙점 1차 보정값은 `uwb_calibration.json`에 있으며, `uwb_live_bridge.py`가 최근 거리 중앙값과 보정값을 적용해 `/api/uwb/distances`로 전송합니다.
## 전체 구조

```text
firmware/
  helmet_av_device/       ESP32-S3-CAM, OV5640, INMP441, MAX98357A, 버튼
  uwb_position_device/    안전모 UWB 태그, 거리 측정과 서버 전송
  uwb_anchor/             현장 고정 UWB 앵커
backend/                  FastAPI, SQLite, 위험도·위치·이벤트·진단 서비스
frontend/                 React/Vite 실시간 관리자 웹
simulator/                실제 장치와 같은 API로 mock 데이터 전송
sample_data/              기본 현장/앵커/위험구역 예시
docs/                     제작·배선·업로드·진단·협업 A-to-Z 문서
```


## 네 개의 A to Z 가이드

1. docs/PROJECT_A_TO_Z_GUIDE.md - 전체 일정, 통합 순서, 시연과 완료 기준
2. docs/HARDWARE_A_TO_Z_GUIDE.md - 전원, 배선, 안전모, AV/UWB 제작과 진단
3. docs/SOFTWARE_A_TO_Z_GUIDE.md - 설치, 서버, 웹, API, 테스트와 문제 해결
4. docs/TEAM_PARTS_A_TO_Z_GUIDE.md - 담당 파트, 파일 소유권, 인수인계와 AI 요청법

## 고정 공통 ID

```json
{
  "organization_id": "org-001",
  "site_id": "site-001",
  "map_id": "map-001",
  "worker_id": "worker-001",
  "helmet_id": "helmet-001",
  "assistant_device_id": "helmet-001-av",
  "position_device_id": "helmet-001-uwb",
  "uwb_tag_id": "tag-001"
}
```

팀원이 내부 알고리즘을 바꿀 수는 있지만 위 ID 필드, `backend/app/schemas/api.py`의 필드 이름, 공개 API 경로와 `frontend/src/types/index.ts` 타입은 함께 승인하지 않는 한 변경하지 않습니다.

## 구현된 1차 기능

- 장치 등록/heartbeat, 상태·배터리·RSSI·부품 진단
- JPEG 이미지 수신과 dummy YOLO 결과 구조
- WAV/PCM 업로드 구조, dummy STT, RapidFuzz 명령 보정
- 버튼 single/double/triple/long 이벤트와 triple 비상 100점
- UWB 앵커 3개 이상 최소제곱 위치 계산, 중앙값+EMA 필터
- 사각형/원형/다각형 위험구역 판정 기반과 3회 연속 진입/이탈 확정
- 보호구·화재·연기·구역·배터리·오프라인·비상 위험도
- WebSocket 대시보드 갱신과 서버→안전모 명령 채널
- 지도, 작업자 상세, 이벤트 확인/종료, 장치 관리, 진단 화면
- mock/hardware 모드와 시나리오 버튼
- 실제 ESP32 연결을 위한 최종 통합 PlatformIO 펌웨어 골격

## 현재 mock 또는 보드 확정 전인 부분

- YOLO 모델 파일이 없을 때 dummy detection을 사용합니다. 실제 모델 연결 지점은 `backend/app/services/yolo_service.py`입니다.
- faster-whisper/VOSK가 없을 때 dummy STT를 사용합니다. 연결 지점은 `backend/app/services/audio_service.py`, `speech_service.py`입니다.
- DW3000 제조사/보드별 라이브러리가 확정되기 전에는 태그가 `uwb_mock.cpp`를 사용합니다. 실제 TWR 구현은 `uwb_dw3000_adapter.cpp`만 교체합니다.
- ESP32-S3-CAM의 OV5640 핀맵은 보드 회로도 확인 전 `ENABLE_CAMERA_HARDWARE=false`입니다.
- INMP441/MAX98357A I2S 드라이버의 실제 DMA 처리는 선택한 Arduino Core 버전에 맞춰 adapter 내부를 완성해야 합니다.

## 실제 하드웨어 연결 순서 요약

1. `docs/HARDWARE_A_TO_Z_GUIDE.md`를 읽고 보드 회로도와 핀 중복을 먼저 확인합니다.
2. 배터리→TP4056→TPS61088 순서로 배선하고, 부하를 연결하지 않은 상태에서 출력이 5.0V인지 멀티미터로 확인합니다.
3. 전원을 끈 상태에서 모든 GND를 공통으로 묶고 AV 보드의 마이크, 앰프, 버튼과 카메라를 연결합니다.
4. `firmware/helmet_av_device/src/config.h`와 UWB 장치 `config.h`의 Wi-Fi, 서버 IP, 실제 핀을 수정합니다.
5. 최종 펌웨어를 업로드하고 시리얼 로그의 `[WIFI]`, `[SERVER]`, `[HEARTBEAT]`, `[CAMERA]`, `[AUDIO]`, `[SPEAKER]`, `[BUTTON]`, `[UWB]`를 확인합니다.
6. 관리자 웹 `하드웨어 진단`에서 두 장치와 앵커의 last_seen, RSSI, 배터리, 부품 상태를 확인합니다.

## 팀원별 수정 위치

- 비전: `backend/app/services/yolo_service.py`, `camera_service.py`, `routers/camera.py`, `firmware/helmet_av_device/src/camera_manager.cpp`
- UWB: `uwb_service.py`, `location_service.py`, `location_filter_service.py`, `routers/uwb.py`, `firmware/uwb_position_device/src/uwb_dw3000_adapter.cpp`
- 음성: `audio_service.py`, `speech_service.py`, `assistant_service.py`, `routers/audio.py`, `audio_recorder.cpp`, `speaker_manager.cpp`
- 통합: `risk_service.py`, `event_service.py`, `command_service.py`, `backend/app/websocket/`, `frontend/src/`

## 검증

```bat
cd backend
..\.venv\Scripts\python -m pytest
cd ..\frontend
npm run build
```

통합 확인은 `run_all.bat` 후 대시보드의 mock 시나리오로 수행합니다. 위험구역 진입, 보호구 미착용, 화재, 연기, 비상, 장치 오프라인을 순서대로 누르고 위치·위험 점수·이벤트·진단 상태가 함께 변하는지 봅니다.

## 첫 Git 커밋

```bat
git init
git checkout -b main
git add .
git commit -m "feat: ESP32 스마트 안전모 1차 통합 시스템"
git checkout -b dev
```

전체 일정은 `docs/PROJECT_A_TO_Z_GUIDE.md`, 하드웨어는 `docs/HARDWARE_A_TO_Z_GUIDE.md`, 소프트웨어는 `docs/SOFTWARE_A_TO_Z_GUIDE.md`, 역할과 협업은 `docs/TEAM_PARTS_A_TO_Z_GUIDE.md`를 따릅니다.

