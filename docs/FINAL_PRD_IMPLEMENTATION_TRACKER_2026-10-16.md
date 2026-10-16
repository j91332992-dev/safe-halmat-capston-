# HANMIR 최종 PRD 적용 및 실물 확인 순서

기준: 사용자 제공 `HANMIR_2.0_CODEX_FINAL_PRD_2026-10-16.md`.
시작점: bc0f779 (P4/모바일 + 10/15 UWB 통합).
작업 브랜치: `integration/hanmir-final-prd-20261016`.

## 1. 이번 단계의 범위

최종 PRD 전체 구현 완료가 아니다. 첫 단계는 운영 기준과 최신성 메타데이터 도입이다.
원격 전체 브랜치를 다시 fetch했으며, 직전 통합 이후 새 원격 변경은 없었다.
브랜치별 비교는 `GITHUB_BRANCH_SYNC_2026-10-16.md`를 함께 참고한다.

- 공통 enum: DataHealth, DetectionState, Priority, IncidentState.
- 버전 있는 최신성 config: `backend/app/services/operating_policy.py`.
- 관리자 인증 API: `GET /api/operating-policy`.
- 기존 장치/작업자 JSON에 `data_health` 추가. 기존 필드 유지.
- heartbeat, camera 수신시각, heading, 마지막 채택 UWB 위치의 나이를 판정.
- 배터리 측정 성공 시각과 YOLO 추론 완료 시각은 아직 연결하지 않아 UNAVAILABLE.
- 실제 측정 시각을 모르는 UWB는 server_acceptance 기준임을 명시.
- verified=false는 이번 정책의 실물 미검증 표시이며, 최신 데이터가 없다는 뜻과 구분한다.
- 사건 enum은 공통 계약이다. 기존 Event 저장/ACK/해결 로직 전체 전환은 아직 하지 않았다.
- 기존 위험 로직은 아직 이 data_health를 강제 조건으로 사용하지 않는다.

## 2. 설정과 경계

`backend/.env`에서 예를 들어 `OPS_HEADING__VALID_SECONDS=2`,
`OPS_HEADING__UNAVAILABLE_SECONDS=5`로 변경한다. 서버 재시작 후 적용된다.
정책 버전은 `OPS_VERSION`으로 기록한다. 실제 .env는 Git에 넣지 않는다.

| 데이터 | VALID 마지막 경계 | STALE 마지막 경계 |
|---|---:|---:|
| heading / UWB | 2초 | 5초 |
| camera / YOLO | 3초 | 10초 |
| battery / heartbeat | 15초 | 30초 |

두 번째 경계 초과는 UNAVAILABLE. 시각 없음·잘못된 시각·미래 시각도 UNAVAILABLE.
DEGRADED는 신선하지만 품질 저하가 확인된 경우를 위한 별도 상태이다.
현재 기존 online 판정 timeout과 새 정책은 아직 통합 전이다. 새 필드만 보고 전체 이관으로 해석하지 않는다.

## 3. 코드에서 확인한 주요 차이

| 영역 | 현재 | 다음 수정 |
|---|---|---|
| UWB | 거리 median 5, 좌표 smoothing, quality/speed observe, 마지막 유효 위치 | PRD jump pending 확인, RMSE 품질, stale 위험확정 금지, 경계 margin |
| UWB 지도 | 수동 XY | 유지. 자동 측량은 P2로 보류 |
| heading | live WebSocket + 보정 | circular EMA와 freshness 일관성 |
| 화재 허가 | 역할/구역/시간대 조건 | 실제 permit/시간/감시자/ROI 검증 |
| PPE | 기존 검출/위험 필드 | 판정 가능한 ROI와 UNKNOWN, 분석 프레임 연속성 |
| 낙상 | 영상 쓰러짐 관련 위험 | 착용자 IMU 낙상과 전방 쓰러짐 별도 사건 |
| 음성 | 서버 STT 후 wake/긴급어/intent | 부정·조건문 오작동, 실패/재질문 상태, 실제값 freshness |
| 사건 | Event open/acknowledged/resolved | 감지 상태와 사건 상태 분리, 우선순위/증거/재알림 |
| 스피커 | 마지막 실물 시험 무음 | 출력부 원인 확인이 필요; 소프트웨어 재생 성공은 청취 성공 아님 |

거리 median_window 5와 PRD의 좌표 median_window 3은 서로 다른 필터이므로 일괄 3으로 바꾸지 않는다.
낙상 3초 목표는 후보/센서 확정 시간과 10초 무응답 승격 시간을 나눠 측정해야 한다.
음성 끝 무음 2초는 단순 조회 3초 목표의 대부분을 소비하므로 초기값 적용 전 후 지연을 각각 측정한다.
전방 카메라 PPE를 안전모 착용자 자신의 PPE로 단정하지 않는다.

## 4. 구현 순서와 완료 기준

1. **공통 기반(이번 단계)**: 최신성/config/상태 계약, 회귀시험. API 필드와 미검증 범위 확인.
2. **위험 사건 기반**: reason_code/evidence, 사이트 분리, 명시적 ACK/RESOLVE, P0/P1 자동 종료 방지. 관리자 재알림 및 실제 통화 연결 결과 구분.
3. **UWB/방향**: 이상점 재확인, 품질/최신성 gate, margin 진입·이탈, 원형 방향 smoothing. 기록 재생으로 기존 위치 기능 비교.
4. **화재/PPE**: 분석 프레임 기준 count, UNKNOWN, permit 조건과 예외 취소. 증거 저장 및 이벤트 연결.
5. **Voice/AI**: 긴급 규칙 우선 저장, 명령 경계/부정문, 단순 조회 tool, stale 응답, 재질문 1회. TTS 실패가 사건 저장을 취소하지 않도록 확인.
6. **P4/낙상**: 실제 accel/gyro sampling과 단위 확인, 후보/확정/응답대기, 데이터 누락 시 판정 금지. 착용자와 전방 쓰러짐 분리.
7. **관리자 웹/앱**: 상태·증거·ACK 표시, 새 APK 버전으로 패키징. 기존 build13이 최신 소스를 포함한다고 가정하지 않는다. iOS 실기 별도 확인.
8. **실물 단위→연동→전체부하**: 아래 순서로 시행하고, 결과에 따라 한 설정씩 변경.

각 단계마다 변경 파일/이유/테스트/실물 여부/남은 문제를 이 문서에 추가한다.
현재 source 정책은 전체 최종 펌웨어가 아니다. 이전 진단 build 디렉터리 산출물을 그대로 flash하지 않는다.

## 5. 안전모 전원을 켠 후 함께 진행할 순서

| 순서 | 사용자 동작 | 확인할 데이터 | 다음 단계 조건 |
|---|---|---|---|
| 1 | P4·태그 USB 연결, 같은 Wi-Fi, 안전모/앵커 켜기 | 포트, firmware_version, IP, heartbeat, 재부팅 원인 | 정상 앱/올바른 서버 확인 |
| 2 | 60초 정지 | 카메라 수신 FPS·frame age, UWB anchor count/RMSE, heading age, battery 측정 성공 | 값이 실제 갱신되는지 확인 |
| 3 | 짧은 확인음 청취 | PCM 송신/수신/쓰기와 실제 청취 결과 | 스피커 청취가 안 되면 음성 안내 완료로 처리하지 않음 |
| 4 | 좌우 90도 회전, 알려진 위치 이동 | 지도 방향/지연, 위치 raw/filtered/P95 | 보정 및 수동 XY 일치 |
| 5 | 사람·보호구가 카메라에 보이게 하기 | 원본/분석 FPS, 판정 가능한 ROI, 검출/UNKNOWN | 카메라·YOLO 개별 확인 |
| 6 | 배터리·위치 질문을 각각 발화 | STT 원문/intent/tool/최신성/응답시간/청취 | 입력 횟수와 처리 건수 비교 |
| 7 | 시험용 SOS·화재 신고 | 사건 저장→관리자 표시→TTS→통화→ACK→종료 | 실제 외부 신고와 구분한 통제 시험 |
| 8 | 통제된 센서 자세 변화 | accel/gyro/후보/확정/취소 | 사람을 실제로 넘어뜨리지 않고 매트/더미로 검증 |
| 9 | 5~10분 동시 사용 | camera freeze/drop, 음성 지연, UWB age, WS 재연결, heap/PSRAM/stack | 단위 성공과 전체부하 성공을 따로 기록 |

사용자가 먼저 준비할 것은 데이터 USB, 동일 네트워크, 실제 밝은 카메라 장면, 앵커 고정이다.
무음 문제가 남으면 현재 납땜을 임의 변경하기 전에 앰프 전원/신호 측정 도구로 확인해야 한다.

## 6. 검증 기록

- 공통 최신성 단위시험: 13 passed.
- frontend production build: 성공.
- 전체 backend 최초 실행: 137 passed / 3 failed / 2 skipped, maxfail=3에서 중단.
- 최초 실패는 가져온 UWB 시험이 관리자 인증이 필요한 GET에 인증 컨텍스트를 주지 않은 데서 발생했다. 두 시험 fixture에서 사이트 의존성을 시험 범위에서만 설정했다. 운영 API 인증은 유지했다.
- 최종 전체 backend 회귀시험: **205 passed, 2 skipped, 18 warnings (32.56초)**. 경고는 남아 있으며 무경고 완료로 표현하지 않는다.
- P4 펌웨어: 이번 단계 변경/빌드/업로드 없음. 실제 전원 시험 없음.
- 서버 실행/DB 마이그레이션/앱 설치: 이번 단계 미실행.
