# 소프트웨어 A to Z 가이드

이 문서는 Windows 설치부터 FastAPI·SQLite·React·시뮬레이터 실행, API 계약, 실제 AI/UWB 전환, 테스트, Git과 문제 해결까지 소프트웨어 전체를 설명합니다.

## 1. 담당 파트

| 파트 | 담당 범위 | 주요 파일 | 완료 기준 |
|---|---|---|---|
| 비전 | 이미지 수신, YOLO, PPE/화재/연기 | `yolo_service.py`, `camera_service.py`, `routers/camera.py` | 프레임 저장, 탐지 JSON, 최근 상태와 웹 표시 |
| 음성·AI | WAV/PCM, STT, 명령 보정, intent | `audio_service.py`, `speech_service.py`, `assistant_service.py`, `routers/audio.py` | 음성 명령 이력과 이벤트/스피커 명령 생성 |
| UWB·위치 | 거리 수신, 좌표·필터·구역 | `uwb_service.py`, `location_service.py`, `location_filter_service.py`, `zone_service.py`, `routers/uwb.py` | 지도 좌표와 confidence, 구역 이벤트 갱신 |
| 통합 백엔드 | DB, 위험도, 이벤트, 명령, WebSocket | `database.py`, `risk_service.py`, `event_service.py`, `command_service.py`, `websocket/` | 모든 기능이 worker/helmet 기준으로 통합 |
| 프론트엔드 | 지도, 상세, 장치, 이벤트, 진단 | `frontend/src/` | 실시간 관리자 화면과 mock/hardware 전환 |
| 테스트·배포 | Windows 배치, pytest, build, Docker | 루트 `.bat`, `backend/tests/`, `docker-compose.yml` | 새 PC에서 설치·실행·검증 가능 |

## 2. 시스템 책임

- ESP32 AV 장치: JPEG/PCM/버튼 수집, Wi-Fi 전송, 명령 수신, 스피커 출력
- ESP32 UWB 태그: 앵커별 거리와 품질 전송
- PC 서버: YOLO, STT, intent, 위치 계산, 필터, 위험구역, 위험도, DB, WebSocket
- React 웹: 현장 지도, 작업자, 장치, 이벤트, 진단과 관리자 명령

ESP32에서 YOLO, STT, 최종 x,y 또는 위험 점수를 계산하지 않습니다.

## 3. Windows 준비

필수:

- Python 3.11 이상
- Node.js 20 이상과 npm
- Git
- Chrome 또는 Edge
- 실제 펌웨어 작업 시 VS Code와 PlatformIO

Python 3.14에서는 SciPy/OpenCV 등 선택 패키지가 제외된 기본 mock 구성이 설치됩니다. 기본 서버·웹·위치 계산은 이 패키지 없이 동작합니다.

## 4. 최초 설치

PowerShell:

```powershell
cd "C:\Users\조성준\OneDrive - pukyong.ac.kr\바탕 화면\한미르\esp32-smart-safety-system"
.\install_windows.bat
```

설치 과정:

1. Python 명령 확인
2. `.venv` 가상환경 생성
3. `backend/requirements.txt` 설치
4. `frontend`에서 `npm install`

설치가 중단되면 마지막 `ERROR` 위쪽의 패키지명과 전체 오류를 보관합니다.

## 5. 실행과 종료

통합 실행:

```powershell
.\run_all.bat
```

열리는 프로그램:

- 백엔드: `http://127.0.0.1:8000`
- 관리자 웹: `http://127.0.0.1:5173`
- 시뮬레이터: 장치 heartbeat와 UWB 이동 데이터 발생

브라우저:

- 웹: `http://localhost:5173`
- API 상태: `http://localhost:8000/api/health`
- Swagger API 문서: `http://localhost:8000/docs`

종료는 열린 세 터미널에서 `Ctrl+C`를 누릅니다.

개별 실행은 `run_backend.bat`, `run_frontend.bat`, `run_simulator.bat`을 사용합니다.

## 6. 폴더 구조와 수정 경계

```text
backend/app/
  models/       SQLAlchemy 테이블
  schemas/      고정 Pydantic 입력 계약
  routers/      공개 API 경로
  services/     팀원이 교체하는 실제 알고리즘
  websocket/    웹/장치 실시간 연결
frontend/src/
  components/   지도·상세·진단·이벤트 UI
  hooks/        snapshot/WebSocket 갱신
  services/     API 호출
  types/        백엔드와 맞춘 TypeScript 타입
simulator/      실제 장치와 같은 API를 보내는 mock
```

`backend/app/schemas/api.py`, 공개 API 경로, `frontend/src/types/index.ts`, 공통 ID는 계약 파일입니다. 알고리즘을 바꿀 때 이 계약은 유지합니다.

## 7. 공통 ID

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

AV 장치와 위치 장치는 같은 `worker_id`, `helmet_id`를 공유하고 서버가 하나의 작업자 상태로 합칩니다.

## 8. 백엔드 시작 흐름

1. FastAPI lifespan에서 SQLite 테이블을 생성합니다.
2. 작업자 1명, 장치 2개, 앵커 4개, 사각형 위험구역 샘플을 넣습니다.
3. router가 장치·카메라·음성·버튼·UWB·구역·위험도·이벤트·진단 API를 제공합니다.
4. 상태 변화 후 WebSocket이 대시보드에 이벤트를 알립니다.
5. React는 snapshot을 다시 가져오며, WebSocket이 끊겨도 5초 주기로 갱신합니다.

## 9. 주요 API

| 기능 | 경로 |
|---|---|
| 장치 등록 | `POST /api/devices/register` |
| heartbeat | `POST /api/devices/heartbeat` |
| 카메라 | `POST /api/camera/frame`, `GET /api/camera/{device_id}/latest` |
| 더미 탐지 | `POST /api/camera/mock-detection` |
| 음성 | `POST /api/audio/upload`, `POST /api/audio/mock-command`, `GET /api/audio/commands` |
| 버튼 | `POST /api/button-event` |
| UWB | `POST /api/uwb/distances` |
| 위치 | `GET /api/locations/{worker_id}/latest`, `/history` |
| 앵커 | `GET/POST /api/anchors`, `PUT/DELETE /api/anchors/{id}` |
| 위험구역 | `GET/POST /api/zones`, `PUT/DELETE /api/zones/{id}` |
| 위험도 | `GET /api/risk/{worker_id}` |
| 이벤트 | `GET /api/events`, acknowledge, resolve |
| 장치 명령 | `POST /api/devices/{device_id}/command` |
| 진단 | `GET /api/diagnostics/summary`, `/devices`, `/{device_id}` |
| 통합 화면 | `GET /api/dashboard/snapshot` |
| 실시간 | `/ws/dashboard`, `/ws/device/{device_id}` |

## 10. 데이터 처리 흐름

### 카메라

OV5640→JPEG→`/api/camera/frame`→파일 저장→YOLO/dummy→PPE/hazard→위험도→웹.

실제 모델은 `yolo_service.py` 안에서만 연결합니다. 모델이 없거나 로딩에 실패하면 같은 출력 스키마의 dummy를 유지합니다. 실제 PPE 판정은 최근 N프레임 투표를 추가해 한 프레임 미탐지로 바로 미착용 처리하지 않습니다.

### 음성

INMP441→PCM/WAV→`/api/audio/upload`→STT/dummy→정규화→명령 사전/RapidFuzz→intent→이벤트/응답→장치 명령.

지원 intent: 관리자 호출, 상태 보고, 위치 조회, 위험도 조회, 도움, 비상, 경고 반복.

### UWB

앵커 거리 3개 이상→품질 가중 Gauss-Newton 최소제곱→최근 중앙값→EMA→지도 범위 보정→confidence→구역 판정.

위치가 튀면 앵커 ID/좌표/단위, 안테나, quality, 원시 거리와 raw/filtered 좌표를 비교합니다.

### 위험구역

사각형, 원형, 다각형 판정 함수를 제공합니다. 3회 연속 내부면 진입, 3회 연속 외부면 이탈로 확정해 경계 튐을 줄입니다.

### 위험도

| 조건 | 점수 |
|---|---:|
| 위험구역 | +30 또는 구역 가중치 |
| 조끼 미착용 | +10 |
| 장갑 미착용 | +5 |
| 연기 | +40 |
| 화재 | +50 |
| 구역 필수 PPE 미착용 | +25 |
| 장치 오프라인 | +10 |
| 배터리 15% 이하 | +10 |
| 낮은 위치 신뢰도 | +10 |
| 버튼/음성 비상 | 즉시 100 |

0~19 정상, 20~39 관심, 40~59 주의, 60~79 위험, 80~100 비상입니다.

## 11. 관리자 웹 사용

### 통합 대시보드

작업자 수, UWB confidence, 최고 위험도, 활성 구역을 확인합니다. 지도에서 작업자를 누르면 위치, PPE, 위험 근거, AV/UWB 장치와 경고 버튼이 표시됩니다.

### 장치 관리

device ID/type, online, IP/RSSI, battery, last_seen을 확인합니다.

### 이벤트

이벤트 시간·등급·메시지·상태를 보고 확인/종료 처리합니다.

### 위험구역

현재 구역과 가중치, 필수 PPE, 경고 메시지를 확인합니다. 좌표 CRUD API는 Swagger에서도 사용할 수 있습니다.

### 하드웨어 진단

장치 online, heartbeat, RSSI, battery, component status, 마지막 카메라/음성/버튼/UWB 수신과 오류를 봅니다.

## 12. Mock 모드 통합 테스트

웹의 시나리오 버튼으로 다음을 확인합니다.

1. 정상 복귀: 안전 위치, PPE 착용, 위험 0
2. 위험구역: 위치·현재 구역·+30·이벤트
3. PPE 미착용: 조끼/장갑 근거 +10/+5
4. 화재: +50과 danger 이벤트
5. 연기: +40과 danger 이벤트
6. 비상: 100과 emergency 이벤트
7. 장치 오프라인: 장치 상태와 +10
8. 음성 명령: intent/이력/응답
9. 버튼 비상: triple press→100
10. 스피커 경고: command가 delivered 또는 queued

별도 테스트 프로젝트 대신 이 최종 흐름을 기준으로 확인합니다.

## 13. Hardware 모드 전환

1. PC와 ESP32를 같은 2.4GHz 네트워크에 둡니다.
2. `ipconfig`의 PC IPv4를 두 펌웨어 `SERVER_BASE_URL`에 입력합니다.
3. Windows 방화벽에서 사설 네트워크 TCP 8000을 허용합니다.
4. 웹 모드를 hardware로 바꿉니다.
5. 두 장치를 부팅하고 register/heartbeat를 확인합니다.
6. 카메라/음성/UWB adapter를 하나씩 실제 구현으로 교체하되 mock 코드는 삭제하지 않습니다.

## 14. 실제 YOLO/STT 선택 설치

Python 3.14에서는 기본 mock 모드로 시작합니다. 실제 모델은 호환 wheel이 있는 Python 3.11~3.13 별도 환경을 권장합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-optional-ai.txt
```

그 후 Ultralytics와 faster-whisper/VOSK를 프로젝트의 모델 선택에 맞춰 설치하고 서비스 내부에서만 연결합니다. 모델 파일이 없을 때 서버가 시작되지 않는 구조로 만들지 않습니다.

## 15. 테스트

백엔드:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

프론트:

```powershell
cd frontend
npm run build
```

통합: `run_all.bat` 후 모든 mock 시나리오, WebSocket 갱신, API `/docs`, 장치 진단을 확인합니다.

## 16. Git 협업

브랜치: `main`, `dev`, `feature/vision`, `feature/uwb`, `feature/voice`, `feature/integration`.

```powershell
git checkout dev
git pull origin dev
git checkout -b feature/vision
git add backend/app/services/yolo_service.py
git commit -m "feat(vision): 실제 YOLO 추론 연결"
git push -u origin feature/vision
```

main 직접 push, API/ID 단독 변경, 담당 외 대규모 수정, mock/diagnostic 삭제, 실행하지 않은 AI 코드 병합을 금지합니다.

계약 변경은 Pydantic schema, router/service, TypeScript type/API/component, 테스트와 문서를 한 PR에서 같이 변경합니다.

## 17. 문제 해결

| 문제 | 확인 | 수정 파일 |
|---|---|---|
| 설치 실패 | Python/Node 버전, 실패 패키지 | `requirements.txt`, `install_windows.bat` |
| 서버 시작 실패 | traceback, 포트 8000, DB 권한 | `main.py`, `database.py`, 해당 router |
| 웹 빌드 실패 | TypeScript 첫 오류 | `types/`, `services/api.ts`, component |
| 화면 갱신 안 됨 | Network, WebSocket, snapshot | `websocket/manager.py`, `useSafetyData.ts` |
| 위험도 이상 | worker state와 reasons | `risk_service.py` |
| 위치 이상 | anchor/거리/raw/filtered | `location_service.py`, `location_filter_service.py` |
| 카메라/음성 API | multipart 필드와 장치 등록 | `routers/camera.py`, `routers/audio.py` |
| 명령 안 옴 | device socket과 command status | `routers/devices.py`, `command_service.py` |

AI에게는 OS와 버전, Git commit, 재현 단계, 기대/실제, Python traceback, 브라우저 Console/Network/WebSocket, ESP32 시리얼, 진단 JSON을 같이 줍니다.

## 18. 완료 기준

- `run_all.bat`으로 세 프로그램이 시작됨
- 웹 지도에 작업자·앵커 4개·위험구역 표시
- 구역 진입과 위험도/이벤트 변화
- 카메라·음성·버튼 mock과 실제 API 경로
- AV/UWB 최종 펌웨어가 같은 서버 계약 사용
- 하드웨어 진단에서 장치와 각 부품 상태 확인
- pytest와 프론트 build 통과
