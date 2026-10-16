# HANMIR 2.0 — Codex 실행용 최종 통합 PRD

작성일: 2026-10-16  
목표: 2026-10-23까지 P4 기반 전체 기능 총통합 및 운영 로직 고정  
시연·최종 데이터 수집: 2026-10-24 ~ 2026-10-26  
저장소: `j91332992-dev/safe-halmat-capston-`

---

# 0. Codex에게 가장 먼저 전달할 지시

이 문서를 프로젝트의 최신 요구사항 기준으로 사용한다.

단, 기존 코드를 전부 다시 만들지 않는다. 먼저 저장소의 모든 브랜치와 현재 구현을 비교하고, 이미 동작하거나 검증된 기능은 최대한 유지한다.

작업 순서는 다음과 같다.

1. 모든 브랜치와 최신 커밋을 확인한다.
2. 현재 실제 구현과 문서상 설계를 구분한다.
3. 최종 통합 기준 브랜치를 만든다.
4. 기존 기능을 보존하면서 이 PRD의 운영 로직을 반영한다.
5. 모든 threshold/timeout/count는 config에서 수정 가능하게 만든다.
6. 실제 장치에서 검증하지 않은 기능은 `verified=false` 또는 `UNVERIFIED`로 표시한다.
7. 변경 후 build/test/실물 시험 결과를 문서에 계속 기록한다.
8. 10/23까지 기능별 실제 시험으로 수치를 조정한다.
9. 10/24~26에는 구조를 크게 바꾸지 않고 시연·데이터 수집·버그수정에 집중한다.

최종 목표는 “기능이 존재한다”가 아니라 다음 질문에 답할 수 있는 시스템이다.

> 어떤 상황에서, 어떤 데이터를 근거로, 어떤 수치와 시간 조건을 만족하면, 어떤 위험으로 판단하고, 누구에게 어떤 순서로 알리며, 언제 사건을 종료하는가?

---

# 1. 현재 GitHub 상태

2026-10-16 기준 확인된 원격 브랜치:

| 브랜치 | HEAD | 의미 |
|---|---|---|
| `main` | `389317e` | 기존 PC 중심 기준본 |
| `feature/mobile-safety-app-20261001` | `0e8a68f` | P4/C6/CSI/음성/모바일 기반 |
| `integration/p4-mobile-live-heading-20261010` | `722c9fd` | P4 + 모바일 + 카메라 + live heading + 통화 등 가장 큰 통합 흐름 |
| `codex/uwb-stabilization-handoff-20261015` | `5bb4c67` | UWB 안정화 및 비교 실험 최신 작업 |
| `codex/integrated-worker-app-20261009` | `4657857` | 관리자/근로자 앱 통합 흐름 |
| `codex/integrated-worker-app-v1.8-build10-20261010` | `775d06f` | v1.8 앱 릴리스 패키지 |
| `codex/integrated-worker-app-v1.8-web-ui-20261010` | `51d555c` | 데스크톱 웹 UI 최신 흐름 |
| `codex/mobile-app-handoff-20261006` | `0191964` | 모바일 UI/멀티사이트 인수인계 |
| `codex/hanmir-final-v1.5-build6-20261007` | `587a5a4` | iOS v1.5 build 6 패키지 |
| `ios-ipa-package-20261002` | `25310eb` | iOS IPA 패키지 전용 |
| `feat/uwb-heartbeat-and-audio-playback-stabilization` | `50d19e2` | UWB heartbeat, audio playback 안정화, 화재 로직 일부 |
| `agent/complete-safety-voice-ui` | `e0e2468` | 기존 음성·안전 UI 흐름 |

## 브랜치 통합 원칙

- `main`이 최신이라고 가정하지 않는다.
- `integration/p4-mobile-live-heading-20261010`을 전체 통합의 1차 기준 후보로 본다.
- `codex/uwb-stabilization-handoff-20261015`의 UWB 변경을 별도로 검토한다.
- 모바일/웹/UI 브랜치의 최신 변경을 비교한다.
- iOS/Android 릴리스 산출물 브랜치와 기능 소스 브랜치를 구분한다.
- 근로자용 앱 관련 브랜치는 존재하지만, 근로자용 앱을 최종 필수범위로 볼지는 아직 확정하지 않는다.
- 최종 통합 전 diff/commit history를 모두 확인한다.

---

# 2. 현재 프로젝트 전체 상태

HANMIR 2.0은 다음 기능을 하나의 현장 안전관리 시스템으로 통합하는 프로젝트다.

- ESP32-P4 기반 스마트 안전모
- OV5647 실시간 카메라
- YOLO 사람/PPE/불꽃/연기/쓰러짐 분석
- INMP441 음성 입력
- STT
- Wake word `투투스`
- 긴급어 우회
- AI Agent
- TTS
- MAX98357A + speaker
- 관리자 ↔ 작업자 통화
- UWB 위치
- BNO085 방향
- 낙상 감지
- MAX17048 배터리
- 위험구역
- 작업자/출입권한/작업허가
- FastAPI
- SQLite
- WebSocket
- 관리자 Web/PWA
- Android/iOS 앱 구조

현재 상태는 “기능 목록” 수준에서 “운영 로직” 수준으로 넘어가는 단계다.

---

# 3. HW 기준

## 최종 기준 하드웨어

- `DFRobot FireBeetle 2 ESP32-P4 / DFR1172`
- `OV5647 MIPI CSI`
- `INMP441`
- `MAX98357A + 8Ω speaker`
- `MAX17048`
- `SW6106`
- `BNO085`
- 기존 ESP32 + DW3000 UWB Tag
- 기존 UWB Anchor
- DFR1172 내장 ESP32-C6
- ESP32-C5는 필요 시 예비

## 역할 분리

```text
P4:
- Camera
- Audio
- BNO085
- Battery
- C6 Network

UWB ESP32:
- DW3000 ranging
- 자체 Wi-Fi
- 서버에 직접 위치 데이터 전송

Server PC:
- FastAPI
- DB
- YOLO
- STT
- AI Agent
- Risk Logic
- Event
- Web/PWA/App
```

## 현재 배선 기준

### INMP441

- BCLK GPIO31
- WS GPIO34
- DATA GPIO36

### MAX98357A

- BCLK GPIO20
- WS GPIO21
- DIN GPIO22

### MAX17048

- I2C1
- SCL GPIO32
- SDA GPIO33
- Address `0x36`

### BNO085

- UART
- P4 RX GPIO23
- P4 TX GPIO51

### OV5647

- MIPI CSI
- SCCB GPIO7/8

### UWB

- P4 data GPIO 없음
- 자체 Wi-Fi

실물 검증 전까지 배선 후보를 절대 “완전 검증됨”으로 표시하지 않는다.

---

# 4. 현재 구현에서 반드시 살릴 것

## UWB

- Anchor 거리 기반 2D 위치 계산
- 최소 3 Anchor
- Weighted Gauss-Newton 위치 계산
- 최근 좌표 Median
- 정지/이동 상태
- EMA
- 위험구역 진입/이탈 연속 확인
- 위치 이력
- WebSocket 지도 전달

## Camera/YOLO

- 최신 원본 JPEG 유지
- 분석 대기 프레임 1장
- 원본 live view와 분석 결과 분리
- 사람/PPE/flame/smoke/fallen
- 위험 증거 저장
- 분석하지 못한 프레임 backlog 방지

## BNO085

- Quaternion
- Yaw/Pitch/Roll
- live heading
- 지도 방향 화살표
- heading calibration

## Voice

- VAD
- PCM/WAV
- STT
- Wake session
- `투투스`
- 긴급어 Wake bypass
- intent
- TTS
- 통화
- 중복 실행 gate
- 위험상태를 AI 응답보다 먼저 저장

## Backend/App

- FastAPI
- DB
- WebSocket
- PWA
- 모바일/iPad UI
- Android/iOS wrapper
- 로그인
- 멀티사이트
- Online/Offline
- reconnect
- NO FRAME
- battery UI

---

# 5. 최종 공통 운영 모델

## Data Health

```text
VALID
DEGRADED
STALE
UNAVAILABLE
```

## Detection State

```text
NORMAL
SUSPECT
CONFIRMED
CLEARED
```

## Priority

```text
P0 EMERGENCY
P1 CRITICAL
P2 WARNING
P3 INFO
```

## Incident State

```text
OPEN
→ ACKNOWLEDGED
→ RESOLVED
```

감지 상태와 사건 상태를 섞지 않는다.

---

# 6. 공통 위험 우선순위

```text
P0:
SOS / 생명위험 / 대형화재 / 화재 음성신고 / 낙상 후 무응답

P1:
확정 화재 / 확정 낙상 / 고위험 무단진입

P2:
PPE 미착용 / 일반 위험구역 무단진입 / 배터리 부족 / 장치 이상

P3:
정상 출입 / 상태변화 / 허가 작업 기록
```

동시에 발생하면:

```text
P0 > P1 > P2 > P3
```

---

# 7. 데이터 최신성

초기값:

| 데이터 | VALID | STALE | UNAVAILABLE |
|---|---:|---:|---:|
| BNO heading | 0~2s | 2~5s | >5s |
| UWB | 0~2s | 2~5s | >5s |
| Camera | 0~3s | 3~10s | >10s |
| YOLO | 0~3s | 3~10s | >10s |
| Battery/heartbeat | 0~15s | 15~30s | >30s |

---

# 8. UWB 운영 로직

## 현재값 유지

```yaml
median_window: 3
stationary_radius_m: 0.15
movement_start_m: 0.30
movement_confirm_count: 2
ema_alpha: 0.65
stationary_delta_m: 0.08
stationary_confirm_count: 5
zone_enter_count: 3
zone_exit_count: 3
min_anchor_count: 3
```

## Outlier Reject 추가

초기:

```text
allowed_jump = 0.5m + 4.0m/s × dt
```

처리:

1. 첫 큰 jump → pending
2. 다음 위치가 pending 좌표 0.75m 이내 → 실제 이동 가능성 인정
3. 다음 위치가 기존 위치 근처 → jump 폐기
4. raw 값은 로그 유지

## 품질

초기:

```text
RMSE <= 0.50m → VALID
0.50m < RMSE <= 1.00m → DEGRADED
RMSE > 1.00m → 단독 위험확정 근거로 사용하지 않음
```

## Anchor 부족

- 3개 이상: 계산
- 2개 이하: 새 위치 계산 X
- 마지막 위치만 STALE 표시
- 5초 이상 → UWB_UNAVAILABLE
- stale position으로 새로운 위험구역 침입 사건 생성 금지

## 위험구역 Hysteresis

```text
zone_margin = max(0.30m, 현장 UWB stationary P95)
```

진입:

```text
margin 이상 내부
+ 3회 연속
```

이탈:

```text
margin 이상 외부
+ 3회 연속
```

---

# 9. UWB 테스트

## 정지

각 위치 60초.

기록:

- raw X/Y
- filtered X/Y
- median error
- P95
- max jump
- dropout
- RMSE

## 이동

- 직선 10회
- 사각 경로 10회
- 위험구역 진입/이탈 20회
- 느린 이동
- 빠른 이동

## 전파방해

- 케이스 없음
- 케이스 있음
- 사람 몸
- 벽
- 기둥
- 금속
- P4 근처
- 배터리 근처

케이스 목표:

```text
P95 error 증가 <= 20%
dropout 증가 <= 2%p
```

---

# 10. UWB Anchor 자동/반자동 지도

```text
Anchor install
→ Anchor간 ranging
→ relative coordinate solve
→ preview
→ 관리자 확인
→ 저장
```

기준:

```text
A1 = (0,0)
A2 = (d12,0)
A3 = +Y 쪽 해 선택
A4+ = least squares
```

잔차가 크거나 Anchor가 거의 일직선이면 자동 저장 금지.

---

# 11. BNO085 방향

현재 유지:

- rotation vector
- quaternion
- yaw/pitch/roll
- 약 10Hz
- server update
- map arrow
- calibration offset

추가:

```text
circular EMA alpha = 0.35
```

목표:

```text
정지 median error <= 10°
90° 회전 error <= 15°
```

---

# 12. 낙상 감지

초기 sampling:

```text
accel >= 50Hz
gyro >= 50Hz
orientation 20~50Hz
```

초기 후보값:

```text
low acceleration: |a| < 0.8g
impact: |a| > 2.0g
rapid rotation: |ω| > 120 deg/s
tilt change: >45° within 1s
abnormal posture: tilt >45° for >=2s
evidence window: 1.5s
```

FALL_SUSPECT:

1.5초 안에 다음 중 2개 이상:

- low acceleration
- impact
- rapid rotation
- large tilt change

FALL_CONFIRMED:

- abnormal posture 2s
또는
- impact + posture change + movement decrease
또는
- worker SOS

Worker confirmation:

> 낙상이 감지되었습니다. 괜찮으시면 ‘괜찮아요’라고 말씀해 주세요.

10초 response window.

- 괜찮아요 + 센서 정상 → resolve candidate
- 무응답 → P0/P1
- 살려줘 → 즉시 P0

---

# 13. 낙상 테스트

- 고개 빠르게 돌리기
- 숙이기
- 쪼그리기
- 뛰기
- 급하게 앉기
- 안전모 벗기
- 안전모 단독 낙하
- 매트/더미 기반 통제 낙상

목표:

```text
fall recall >= 90%
ADL false positive <= 5%
decision latency <= 3s
```

---

# 14. Camera / YOLO

현재 confidence 초기값:

```yaml
general_candidate: 0.25
person: 0.35
helmet: 0.45
vest: 0.40
glove: 0.40
flame: 0.75
smoke: 0.45
```

---

# 15. PPE

상태:

```text
WORN
MISSING
UNKNOWN
```

UNKNOWN:

- 사람 너무 작음
- 손/body ROI 가림
- frame 밖
- blur
- stale camera
- 필요한 신체부위 visibility 부족

MISSING:

판정 가능한 상태에서 required PPE가 3 analyzed frames 연속 미검출.

Clear:

```text
2회 연속 WORN
+ 약 2초 유지
```

Risk:

- 일반 zone: P2
- high-risk + required PPE missing: P1 가능
- worker TTS
- admin alert
- evidence frame
- 동일 PPE TTS cooldown 120s

---

# 16. 전방 작업자 쓰러짐

현재:

- fallen class
또는
- bbox aspect ratio >= 1.5
- 약 3초

반드시 분리:

```text
CAMERA_PERSON_DOWN
!=
WEARER_FALL
```

---

# 17. 화재

Candidate:

- flame >= 0.75
- smoke >= 0.45
- 음성 화재신고

Video Confirm:

```text
flame >= 0.75 for 3 analyzed frames
smoke >= 0.45 for 2 analyzed frames
```

Critical:

- 음성 화재신고
- confirmed flame + confirmed smoke
- flame area ratio >= 0.15
- flame growth ratio >= 0.20
- 허가작업 ROI 밖 confirmed flame
- 정상 화기작업 중 주변 착화/확산

---

# 18. 허가된 화기작업

정상 화기작업 예외는 전부 충족:

```text
permit.active
worker_id match
zone_id match
current time within permit
work type match
flame inside hot_work_roi
```

필요한 작업이면:

```text
fire_watcher_required = true
→ fire_watcher_assigned = true
```

예외 해제:

- confirmed smoke
- large fire
- ROI 밖 flame
- rapid flame growth
- worker fire report
- admin fire report

---

# 19. 화재 대응

## SUSPECT

- 내부 log
- analysis priority 증가
- 관리자 UI `화재 의심`

## CONFIRMED / P1

1. incident OPEN
2. current location
3. current frame
4. annotated frame
5. admin Critical
6. worker TTS
7. evacuation route 가능 시 계산

## P0

대형화재 또는 음성신고:

1. incident immediate OPEN
2. admin Emergency
3. worker immediate evacuation TTS
4. exit guidance
5. manager call
6. ACK 전 반복

초기:

```text
관리자 미확인 10s → 재알림/call
ACK 전 repeat 15s
ACK 후 status update 60s
```

Fire Clear:

```text
30s continuous no flame/smoke
→ CLEARED_CANDIDATE
```

P0/P1 incident는 관리자 확인 후 RESOLVED.

---

# 20. Voice / Wake / STT

기본 흐름:

```text
Mic
→ VAD
→ short pre-roll
→ WAV
→ Server STT
→ wake/emergency
→ intent
→ action
→ response/TTS
```

일반명령:

- `투투스`/별칭 포함
- wake follow-up session active

아니면 일반 대화 무시.

Emergency bypass 예:

- 살려줘
- 살려주세요
- 도와줘
- 비상상황
- 불이야
- 불났어
- 화재
- 다쳤어
- 기계에 끼었어
- 숨을 못 쉬겠어

---

# 21. Voice recording

초기:

```yaml
sample_rate: 16000
bit_depth: 16
channels: 1
pre_roll_ms: 300
end_silence_ms: 2000
max_clip_ms: 8000
followup_seconds: 20
duplicate_window_seconds: 3
upload_retry_count: 3
```

---

# 22. Voice failure

STT empty/이해 실패:

1. “잘 듣지 못했습니다. 다시 한 번 말씀해 주세요.”
2. 새 음성 1회 재녹음
3. 재실패 → “명령을 확인하지 못했습니다.”
4. session 종료

STT/API/Network error:

- 이해 실패와 구분
- error log
- reconnect
- 임의 답 생성 금지
- 이미 확정된 safety incident 취소 금지

---

# 23. Structured Query

LLM 추론 없이 실제 서버값 사용:

- 위치
- 배터리
- 방향
- 위험도
- PPE
- device connection
- recent alert
- current zone
- access permission
- nearest exit
- work permit
- work time

---

# 24. AI Agent

Tier 0 — Safety Rule:

- SOS
- fire report
- emergency
- manager call
- stop speaking
- hang up

Tier 1 — Structured Assistant:

```text
get_worker_status()
get_worker_location()
get_worker_heading()
get_battery()
get_ppe_status()
get_open_incidents()
get_zone_status()
get_access_permission()
get_nearest_exit()
get_work_permit()
get_work_time()
```

Tier 2 — Reasoning Assistant:

- 지금 위험한 거 있어?
- 지금 어디로 이동해야 해?
- 현재 상황을 관리자에게 요약해줘.

AI 제한:

- 없는 데이터 추측 X
- stale 값을 current처럼 표현 X
- permit 생성 X
- access approval 생성 X
- P0/P1 auto resolve X
- AI 장애가 Tier0 Safety Rule을 막으면 안 됨

---

# 25. 위험구역

Zone 데이터:

```text
zone_id
zone_type
geometry
severity
required_ppe
authorized_workers
required_permits
```

UWB에서 margin 내부 + 3회:

→ 진입.

권한 있음:

→ INFO.

권한 없음:

→ P2/P1.

---

# 26. Work Permit

```text
permit_id
permit_type
worker_ids
zone_id
valid_from
valid_until
approved_by
fire_watcher_required
fire_watcher_id
hot_work_roi
status
```

초기:

- 만료 10분 전 관리자 INFO
- 만료 후 계속 작업 감지 → Warning

---

# 27. Worker / Work Time

Worker:

```text
worker_id
role
qualification
training_status
site_access
zone_access
active_permits
shift_start
shift_end
breaks
```

근로시간은 `work_policy`로 관리:

```text
max_shift_minutes
break_rules
overtime_policy
night_work_policy
```

---

# 28. Battery / Device

MAX17048:

```text
<=30% → LOW / P3
<=15% → BATTERY WARNING / P2
read failure → null/error
```

Heartbeat:

```text
5s interval
15s no receive → STALE
30s no receive → OFFLINE
```

Reconnect:

```text
3s → 5s → 10s → 20s
```

---

# 29. 경보 Matrix

| 사건 | 작업자 | 관리자 | 통화 | 저장 |
|---|---|---|---|---|
| PPE missing | TTS | Warning | X | frame/event |
| unauthorized zone | TTS | Warning/Critical | 조건부 | location/event |
| UWB unavailable | 상태안내 | Warning | X | device log |
| battery <=15% | TTS | Warning | X | device log |
| fall suspect | 확인질문 | Warning | 무응답 시 | IMU/location |
| fall confirmed | urgent TTS | Critical | O | IMU/location |
| fire confirmed | evacuation TTS | Critical | O/조건 | frame/location |
| major fire/report | immediate evacuation | Emergency | O | full evidence |
| voice SOS | emergency response | Emergency | O | location/event |

---

# 30. 대표 시나리오

## 정상 허가 용접

```text
UWB zone entry
→ access OK
→ hot-work permit OK
→ time OK
→ fire watcher condition OK
→ flame inside ROI
→ INFO only
```

## 정상 용접 중 주변 착화

```text
normal hot-work
→ flame/smoke outside ROI
→ permit exception cancelled
→ FIRE CONFIRMED
→ worker evacuation
→ admin Critical
→ evidence
```

## 무단 위험구역

```text
UWB inside x3
→ worker
→ permission false
→ warning
→ worker TTS
→ admin
→ DB
```

## PPE missing

```text
person visible
→ required helmet
→ 3 analyzed frames missing
→ MISSING
→ alert
→ helmet visible x2 + 2s
→ cleared
```

## PPE occluded

```text
required body ROI invisible
→ UNKNOWN
→ no missing incident
```

## Fall

```text
multi IMU evidence
→ SUSPECT
→ TTS question
→ no response 10s
→ P0/P1
→ location
→ admin
→ call
```

## SOS

```text
"살려줘"
→ no wake required
→ P0
→ location
→ admin
→ call
```

## Simple Query

```text
"투투스 배터리 얼마야?"
→ STT
→ battery tool
→ freshness
→ response
```

## Complex Query

```text
"투투스 지금 위험한 거 있어?"
→ incidents
→ UWB
→ PPE
→ fire
→ zone
→ permit
→ Agent summary
```

---

# 31. Logging

Common:

- test_id
- event_id
- site_id
- worker_id
- device_id
- firmware_version
- server_version
- device timestamp
- server timestamp

UWB:

- raw/calibrated ranges
- anchor count
- raw/filtered X,Y
- RMSE
- reject reason
- zone state

Camera:

- frame_id
- resolution
- receive/analyze time
- class/confidence
- bbox
- consecutive count
- area/growth

IMU:

- accel XYZ
- gyro XYZ
- orientation
- threshold hit
- state

Voice:

- VAD
- start/end
- clip duration
- end reason
- STT latency
- transcript
- wake session
- intent
- retry
- total latency

Agent:

- called tools
- each data timestamp
- model
- timeout/fallback
- final response

---

# 32. 공통 Config 예시

```yaml
uwb:
  median_window: 3
  stationary_radius_m: 0.15
  movement_start_m: 0.30
  movement_confirm_count: 2
  ema_alpha: 0.65
  stale_seconds: 2
  unavailable_seconds: 5
  enter_count: 3
  exit_count: 3
  min_zone_margin_m: 0.30
  outlier_base_m: 0.5
  outlier_speed_mps: 4.0
  outlier_confirm_radius_m: 0.75

orientation:
  stale_seconds: 2
  smoothing_alpha: 0.35

camera:
  candidate_conf: 0.25
  person_conf: 0.35
  helmet_conf: 0.45
  vest_conf: 0.40
  glove_conf: 0.40
  flame_conf: 0.75
  smoke_conf: 0.45
  flame_confirm_frames: 3
  smoke_confirm_frames: 2
  ppe_missing_frames: 3
  ppe_clear_frames: 2
  large_fire_area_ratio: 0.15
  flame_growth_ratio: 0.20

voice:
  sample_rate: 16000
  pre_roll_ms: 300
  end_silence_ms: 2000
  max_clip_ms: 8000
  followup_seconds: 20
  retry_count: 1
  duplicate_window_seconds: 3
  upload_retry_count: 3

fall:
  sample_hz: 50
  low_accel_g: 0.8
  impact_accel_g: 2.0
  angular_velocity_dps: 120
  tilt_change_deg: 45
  evidence_window_ms: 1500
  abnormal_posture_seconds: 2
  worker_response_seconds: 10

device:
  heartbeat_seconds: 5
  stale_seconds: 15
  offline_seconds: 30

alerts:
  p0_duplicate_seconds: 15
  p1_duplicate_seconds: 30
  p2_voice_cooldown_seconds: 120
  manager_p0_ack_seconds: 10
```

---

# 33. 테스트 계획 — 10/23까지

Phase 1 — Unit:

- P4
- C6
- OV5647
- YOLO
- INMP441
- STT
- AI Agent
- MAX98357A
- MAX17048
- BNO085
- UWB
- App/Web

Phase 2 — Pair:

- Camera + YOLO
- UWB + BNO
- Voice + Agent
- P4 + Server
- Risk + App
- TTS + call

Phase 3 — Scenario:

대표 시나리오 반복.

Phase 4 — Full Load:

```text
Camera
YOLO
Wi-Fi
Voice
STT
TTS
UWB
BNO
Battery
Risk
DB
Web/App
```

---

# 34. 10/23 프로젝트 목표

이 수치는 인증기준이 아니라 팀 내부 목표다.

UWB:

```text
LOS stationary median error <= 0.30m
P95 <= 0.75m
dropout < 5%
zone false event 0/20 목표
```

Voice:

```text
quiet command success >= 95%
noise command success >= 85%
emergency recall >= 95%
unintended command <= 2%
simple query median response <= 3s
```

YOLO:

```text
PPE recall >= 90% 목표
fire/smoke recall >= 90% 목표
false alarm <= 5% 목표
```

Fall:

```text
controlled fall recall >= 90%
ADL false positive <= 5%
decision <= 3s
```

Network:

```text
server recovery reconnect <= 10s 목표
offline detection <= 30s
```

Alert:

```text
P0 confirmed → admin UI <1s 목표
P0 confirmed → worker TTS start <2s 목표
```

---

# 35. Threshold 조정 원칙

한 번에 하나만 변경한다.

항상 기록:

```text
Before
After
Reason
Test data
Result
Adopt/Reject
```

---

# 36. 10/24~26

23일까지 기능/운영 로직을 최대한 고정한다.

24일부터:

```text
실제 시연
→ 영상 촬영
→ 성능값 수집
→ 오류 수정
→ 재시연
```

큰 신규 기능은 가급적 추가하지 않는다.

---

# 37. Worker App

브랜치에 관련 코드가 있어도 최종 필수 기능으로 확정하지 않는다.

팀 합의 후 결정.

우선순위는 관리자 App + 안전모 완성.

---

# 38. 구현 우선순위

P0:

- branch 통합
- P4 실물 안정화
- data freshness
- SOS
- fire
- fall
- P0/P1 alerts
- incident lifecycle

P1:

- UWB outlier/hysteresis
- PPE UNKNOWN
- Hot-work permit
- heading
- structured Agent tools
- voice retry/error state

P2:

- Anchor auto map
- worker work-time
- Worker App
- heavy-equipment/opening AI

P2가 P0/P1을 지연시키면 제외 가능.

---

# 39. Codex 구현 규칙

1. 기존 동작 기능을 확인 없이 삭제하지 않는다.
2. 모든 브랜치를 확인한다.
3. `main`을 최신이라고 가정하지 않는다.
4. 실제 검증과 코드 존재를 구분한다.
5. threshold를 하드코딩으로 흩뿌리지 않는다.
6. config + version으로 관리한다.
7. 모든 위험판정에 `reason_code`와 `evidence`를 남긴다.
8. stale/unavailable을 정상값으로 취급하지 않는다.
9. AI가 Safety Rule을 대체하지 않는다.
10. 실물 미검증 기능은 미검증 상태를 UI/API에서 확인 가능하게 한다.
11. 기능 추가보다 regression 방지를 우선한다.
12. 변경 후 frontend build/backend tests/P4 build/실물시험 범위를 각각 기록한다.

---

# 40. 권장 Reason Code

```text
FIRE_FLAME_CONSECUTIVE
FIRE_SMOKE_CONSECUTIVE
FIRE_VOICE_REPORT
FIRE_HOTWORK_EXCEPTION
FIRE_OUTSIDE_HOTWORK_ROI

PPE_HELMET_MISSING
PPE_HELMET_UNKNOWN
PPE_VEST_MISSING

UWB_INSUFFICIENT_ANCHORS
UWB_OUTLIER_REJECTED
UWB_STALE
ZONE_UNAUTHORIZED_ENTRY

FALL_MULTI_EVIDENCE
FALL_NO_WORKER_RESPONSE
FALL_CANCELLED_BY_RESPONSE

VOICE_STT_EMPTY
VOICE_STT_SERVICE_ERROR
VOICE_UNKNOWN_INTENT
VOICE_RETRY_FAILED

DEVICE_HEARTBEAT_STALE
DEVICE_OFFLINE
```

---

# 41. API/Event 공통 구조 권장

```json
{
  "event_id": "uuid",
  "site_id": "site-001",
  "worker_id": "worker-01",
  "device_id": "helmet-01",
  "type": "fire",
  "priority": "P1",
  "detection_state": "CONFIRMED",
  "incident_state": "OPEN",
  "reason_codes": [
    "FIRE_FLAME_CONSECUTIVE",
    "FIRE_SMOKE_CONSECUTIVE"
  ],
  "evidence": {
    "flame_confidence": 0.86,
    "smoke_confidence": 0.71,
    "frame_id": 12345,
    "position": {
      "x": 2.4,
      "y": 5.1,
      "age_ms": 340
    }
  },
  "created_at": "ISO-8601"
}
```

실제 schema는 기존 API와 맞춰 최소 변경으로 적용한다.

---

# 42. 최종 완료 정의

10/23에 다음이 되어야 HANMIR 2.0 운영 로직 1차 완료로 본다.

- P4에서 주요 HW가 동작한다.
- 기존 기능 회귀가 없다.
- Camera/YOLO/Voice/UWB/BNO/Battery가 서버로 연결된다.
- Web/PWA/App에서 실제 데이터가 보인다.
- 데이터 stale/offline 상태가 존재한다.
- UWB jump와 경계 흔들림 처리가 있다.
- BNO heading이 지도와 연결된다.
- 낙상 후보/확정/작업자 확인 흐름이 있다.
- PPE MISSING/UNKNOWN을 구분한다.
- 정상 화기작업과 비정상 화재를 구분한다.
- 긴급어는 AI보다 먼저 동작한다.
- 단순조회는 실제 서버값을 사용한다.
- 복합 AI는 Tool 근거만 사용한다.
- P0/P1 alert가 작업자/관리자/DB로 연결된다.
- 사건 ACK/RESOLVE가 존재한다.
- 모든 threshold가 config화돼 있다.
- 주요 판단 로그가 남는다.
- 실제 시험 결과를 기반으로 초기값을 수정한다.

---

# 43. 최종 제품 정의

HANMIR 2.0의 최종 모습은 다음이다.

> 작업자가 안전모를 착용하고 현장을 이동하면 UWB와 BNO085가 위치와 방향을 제공하고, 카메라가 전방 사람·PPE·화재 위험을 분석한다. 마이크는 작업자의 명령과 긴급 신고를 처리한다. 서버는 각 센서의 최신성·신뢰도·작업자 정보·구역·작업허가를 함께 확인하여 위험을 판단한다. 확정된 위험은 우선순위에 따라 작업자 음성안내, 관리자 앱 경보, 통화, 위치·영상·센서 증거 저장으로 연결한다. 위험이 사라져도 사건 이력과 관리자 확인을 유지한다. AI Agent는 이 안전 로직을 대신하지 않고 실제 서버 데이터를 이용해 조회·설명·상황 요약을 제공한다.

---

# 44. Codex가 지금 바로 시작할 첫 작업

1. 현재 원격 모든 브랜치 fetch
2. 각 브랜치 HEAD/diff 목록 작성
3. `integration/p4-mobile-live-heading-20261010` + UWB 최신 브랜치 + 최신 UI 브랜치 비교
4. 최종 통합 브랜치 생성
5. frontend/backend/P4 현재 build baseline 기록
6. 기존 regression test 실행
7. config 구조 생성
8. data health + risk priority + incident state 공통 모델 구현
9. UWB 개선
10. Fire/PPE 개선
11. Voice/Agent 개선
12. BNO/Fall 구현
13. Web/App 연결
14. scenario test
15. full-load test
16. 10/23 결과 문서화

작업이 끝날 때마다 다음을 남긴다.

```text
- 변경 파일
- 변경 이유
- 현재 동작
- 테스트 방법
- 테스트 결과
- 실물 검증 여부
- 남은 문제
- 다음 작업
```

---

## 최종 한 줄

> HANMIR 2.0은 “여러 기능이 들어간 스마트 안전모”가 아니라, 실제 센서의 최신성·신뢰도·작업자·위치·작업허가·위험상황을 함께 판단하고, 정해진 기준과 우선순위에 따라 작업자와 관리자에게 실제 행동까지 연결하는 현장형 통합 안전관리 시스템으로 완성한다.
