# 팀원 담당 파트 A to Z 가이드

이 문서는 팀원이 AI 도구를 사용해 자기 파트를 수정하더라도 통합 계약이 깨지지 않도록 역할, 파일 소유권, 입력·출력, 작업 순서, 완료 조건과 인수인계를 정의합니다.

## 1. 공통 규칙

모든 팀원이 지켜야 할 계약:

- `organization_id`, `site_id`, `worker_id`, `helmet_id`, `device_id`, `uwb_tag_id`를 제거하거나 이름을 바꾸지 않습니다.
- `backend/app/schemas/api.py`의 Pydantic 필드와 `frontend/src/types/index.ts` 타입을 단독 변경하지 않습니다.
- 공개 API 경로와 WebSocket 경로를 임의로 바꾸지 않습니다.
- mock mode와 hardware diagnostic을 삭제하지 않습니다.
- 담당 service/adapter 내부 실제 구현 교체를 우선합니다.
- 별도 부품 테스트 프로젝트를 만들지 않고 최종 서버·웹·펌웨어에서 확인합니다.
- PR에 재현 방법, 실행 명령, 로그, 테스트 결과와 현재 mock 부분을 적습니다.

## 2. 전체 역할표

| 역할 | 책임 | 소프트웨어 파일 | 펌웨어 파일 |
|---|---|---|---|
| 비전 담당 | OV5640/JPEG, YOLO, PPE·화재·연기 | `camera_service.py`, `yolo_service.py`, `routers/camera.py` | AV `config.h`, `camera_manager.cpp` |
| 음성·AI 담당 | INMP441/WAV, STT, 명령 보정, intent, 스피커 | `audio_service.py`, `speech_service.py`, `assistant_service.py`, `routers/audio.py` | `audio_recorder.cpp`, `speaker_manager.cpp`, `websocket_client.cpp` |
| UWB 담당 | 태그·앵커, 거리, x/y, 필터, confidence | `uwb_service.py`, `location_service.py`, `location_filter_service.py`, `routers/uwb.py` | UWB `config.h`, `uwb_interface.h`, `uwb_dw3000_adapter.cpp`, 앵커 펌웨어 |
| 통합 담당 | DB, 위험구역, 위험도, 이벤트, 명령, WebSocket, 웹 | `risk_service.py`, `zone_service.py`, `event_service.py`, `command_service.py`, `websocket/`, `frontend/src/` | `server_client.cpp`, 공통 ID/heartbeat |
| 전원·기구 담당 | 전원부, 배선, 절연, 안전모 장착, 앵커 고정 | 하드웨어 가이드와 진단 기록 | 각 `config.h` 실제 핀표 |
| 테스트·문서 담당 | 설치, 실행, 테스트, Git, 시연과 백업 | `.bat`, `backend/tests/`, 네 개 가이드 | 업로드/시리얼 체크리스트 |

## 3. 비전 담당

### 입력

- `POST /api/camera/frame`
- multipart: `file`, `device_id`, `worker_id`, `helmet_id`
- OV5640 JPEG QVGA/VGA, 목표 1~3FPS

### 출력

```json
{
  "detections": [],
  "ppe": {"vest": true, "glove": true},
  "hazards": {"fire": false, "smoke": false},
  "mode": "dummy 또는 hardware"
}
```

### 작업 순서

1. mock frame API와 최신 이미지 조회가 동작하는지 확인합니다.
2. 실제 보드 회로도 핀을 AV `config.h`에 입력합니다.
3. `camera_manager.cpp`에서 카메라 초기화와 JPEG multipart POST를 완성합니다.
4. `yolo_service.py`에서 모델 존재 여부를 확인하고, 없으면 dummy를 유지합니다.
5. vest/glove는 최근 N프레임 투표, fire/smoke는 즉시 이벤트 정책을 적용합니다.
6. DB 이벤트와 웹 작업자 상세에 결과가 표시되는지 봅니다.

### 완료 조건

- 카메라 초기화 실패 코드가 heartbeat/로그에 보임
- 프레임 업로드 성공/실패 재시도 로그
- 최신 이미지와 탐지 결과가 웹에 표시됨
- 모델이 없어도 서버가 시작되고 mock으로 동작

### AI 요청 예시

> 내 보드는 [정확한 ESP32-S3-CAM 리비전]이고 카메라는 OV5640이다. `camera_manager.cpp`에 QVGA JPEG multipart 업로드를 구현해줘. `config.h` 핀만 사용하고 `/api/camera/frame` 필드, heartbeat, mock mode를 바꾸지 마. 시리얼 로그와 서버 응답은 다음과 같다: …

## 4. 음성·AI 담당

### 입력

- INMP441 16kHz mono 16bit PCM
- single press 또는 서버 `record_audio`
- `POST /api/audio/upload`

### 출력

- STT text
- normalized text
- intent와 confidence
- 이벤트, 사용자 응답과 선택적 스피커 command

### 작업 순서

1. `/api/audio/mock-command`로 intent와 위험도 흐름을 확인합니다.
2. `audio_recorder.cpp`에 Arduino Core 버전에 맞는 I2S DMA와 3~5초 버퍼를 구현합니다.
3. WAV 헤더를 붙여 multipart 업로드합니다.
4. `audio_service.py`에 faster-whisper/VOSK를 연결하되 실패 시 dummy를 유지합니다.
5. `speech_service.py` 명령 사전과 유사도 기준을 보정합니다.
6. `assistant_service.py`에서 상태·위치·위험도 응답과 명령을 만듭니다.
7. `speaker_manager.cpp`에 MAX98357A I2S 출력을 완성합니다.

### 완료 조건

- audio level, 녹음 시작/종료, 업로드 code가 시리얼에 출력됨
- 웹에 원문, intent, confidence, 시간이 표시됨
- “비상”은 위험도 100
- 웹 경고 버튼이 안전모 스피커까지 도달

### AI 요청 예시

> ESP32 Arduino Core [버전] 기준으로 `audio_recorder.cpp`에 INMP441 16kHz mono 16bit 4초 WAV 녹음/업로드를 구현해줘. 핀과 API, mock, diagnostic을 유지하고 다른 서비스는 수정하지 마. 현재 로그: …

## 5. UWB 담당

### 입력

```json
{
  "device_id": "helmet-001-uwb",
  "uwb_tag_id": "tag-001",
  "measurements": [
    {"anchor_id": "anchor-001", "distance_m": 3.2, "quality": 0.95}
  ]
}
```

### 출력

- raw x,y
- filtered x,y
- confidence
- 앵커별 거리 기록과 구역 이벤트

### 작업 순서

1. 시뮬레이터와 `uwb_mock.cpp`로 서버 위치 계산을 확인합니다.
2. 앵커 4개의 고유 ID, 전원과 좌표를 확정합니다.
3. 실제 라이브러리를 `uwb_dw3000_adapter.cpp` 안에서 `IUwbTag`에 맞춰 연결합니다.
4. 앵커별 offset/quality를 기록합니다.
5. `location_service.py` 최소제곱 잔차와 confidence를 검증합니다.
6. `location_filter_service.py`의 median/EMA를 현장 속도에 맞춥니다.
7. 3회 연속 구역 진입/이탈과 지도 경로를 확인합니다.

### 완료 조건

- 유효 앵커 거리 3개 이상이 지속 수신됨
- 위치가 현장 경계 안에서 실제 이동을 따라감
- 낮은 품질/이상치가 confidence에 반영됨
- 태그가 x,y를 계산하지 않고 거리만 보냄

### AI 요청 예시

> 내 UWB 보드는 [제품/리비전], DW3000 라이브러리는 [이름/버전]이다. `uwb_dw3000_adapter.cpp` 안에서만 TWR를 구현하고 `IUwbTag`, JSON, mock을 유지해줘. 앵커/태그 시리얼 로그: …

## 6. 통합 담당

### 책임

- worker/helmet 기준 상태 통합
- 위험구역과 위험도
- 이벤트 생성/확인/종료
- 장치 명령 queue와 device WebSocket
- React 지도·상세·장치·이벤트·진단

### 작업 순서

1. Pydantic/TypeScript 계약과 공통 ID를 보호합니다.
2. 각 router가 service만 호출하고 도메인 책임이 섞이지 않는지 봅니다.
3. 위치·PPE·hazard·device 상태 변화 후 `recalculate_risk`를 호출합니다.
4. DB commit 후 dashboard WebSocket으로 갱신을 알립니다.
5. 프론트는 snapshot 응답을 단일 상태 원본으로 사용합니다.
6. mock/hardware 전환과 모든 시나리오를 유지합니다.
7. 장치 명령은 queued/delivered 상태를 기록합니다.

### 완료 조건

- 한 작업자 상세에 AV와 UWB 상태가 합쳐짐
- 위험 점수, 등급과 근거 합계가 일치
- WebSocket 단절 시에도 주기적 snapshot으로 복구
- 이벤트 확인/종료와 장치 경고가 작동

### AI 요청 예시

> `risk_service.py`의 기존 점수 근거, 0~100 상한, emergency=100을 유지하면서 [규칙]을 추가해줘. Pydantic/TypeScript 계약과 mock 시나리오가 깨지지 않게 pytest와 프론트 build를 실행해.

## 7. 전원·기구 담당

### 책임

- LiPo→TP4056→스위치→TPS61088 5V
- 공통 GND, 커넥터와 절연
- 안전모 무게 균형, 부품 고정과 케이블 정리
- 앵커 전원/위치 고정

### 완료 조건

- ESP32 연결 전 무부하 5.0V 확인
- 스피커 출력/카메라 전송 순간에도 5V 유지
- 쇼트·심한 발열·노출 도체 없음
- 얼굴/목 간섭, 시야 가림, 흔들림 없음
- 실제 핀·전압·좌표 기록을 팀에 전달

## 8. 테스트·문서 담당

### 테스트 명령

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm run build
```

### 통합 시나리오

정상→위험구역→PPE 미착용→화재/연기→음성 비상→버튼 비상→관리자 경고→장치 오프라인/복구 순서로 확인합니다.

### 수집할 증거

- 같은 시간대 서버 로그
- 브라우저 Console/Network/WebSocket
- AV/UWB/앵커 시리얼
- 진단 summary/device JSON
- 화면 캡처
- 전압, 앵커 좌표와 보드/라이브러리 버전

## 9. 브랜치와 인수인계

| 담당 | 브랜치 |
|---|---|
| 비전 | `feature/vision` |
| UWB | `feature/uwb` |
| 음성 | `feature/voice` |
| 통합/웹 | `feature/integration` |

feature→dev PR을 사용하고 main 직접 push는 금지합니다.

인수인계에는 다음을 씁니다.

1. 바꾼 파일과 이유
2. 입력/출력 계약
3. 실제로 실행한 명령
4. 성공/실패 로그
5. 아직 mock인 부분
6. 실제 보드/모델/라이브러리 버전
7. 다음 담당자가 수정할 정확한 함수

## 10. 충돌과 계약 변경

`schemas/api.py`, TypeScript types, 공통 ID 또는 API 경로 충돌은 한쪽을 임의 선택하지 않습니다. 통합 담당과 합의해 백엔드·프론트·펌웨어·테스트·문서를 한 PR에서 같이 변경합니다.

## 11. 팀 완료 체크리스트

- 비전: 실제/더미 탐지 모두 동일 스키마
- 음성: 실제/더미 STT 모두 동일 intent 흐름
- UWB: mock/실제 adapter 모두 동일 거리 스키마
- 통합: 모든 상태가 worker/helmet으로 합쳐짐
- 하드웨어: 전원·핀·장착 기록 완료
- 테스트: pytest, build, 통합 시나리오 통과
- 문서: 네 A to Z 가이드가 현재 코드와 일치
