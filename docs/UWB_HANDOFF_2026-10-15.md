# UWB 안정화 인수인계 — 2026-10-15

다음 작업자가 Codex로 이어갈 코드와 선택한 네 가지 비교 자료다. **위치 정확도와 화면 안정성이 모두 개선됐다고 검증한 상태는 아니다.** 카톡 보고 자료는 이번 공유 범위에 포함하지 않았다.

## 기준과 공유 범위

- 브랜치: `codex/uwb-stabilization-handoff-20261015`
- 시작점: main `389317eeccc342f09471e61cdc4b7eb08c23083f`
- P4 비교 기준: `integration/p4-mobile-live-heading-20261010`, `722c9fd327997b8d4bdd59ae088928d9285eba40`
- P4 전체를 merge한 브랜치가 아니다. 실제 ranging의 clock offset 중복 부호 확장 수정은 포함하지만, P4 인증·다중 사이트·AV 등 전체 기능은 포함하지 않는다. P4 제품 통합 시 별도 대조가 필요하다.
- 현장 지도 크기·앵커 좌표·작업자/장치 등록 DB, 개인 `.env`, Wi-Fi 비밀번호, 장치 플래시와 백업은 제외했다. 소스의 기존 기본 지도 크기 5.8×8.2m는 바꾸지 않았다.
- `config.py`와 `.env.example`의 변경은 UWB 기능 설정이다. 현장 지도 설정과 구분한다. 측정 자료의 2×1m 좌표는 **실험 조건**이며 서버에 자동 적용되지 않는다.
- [선택한 네 가지 측정 자료](measurements/2026-10-15-comparison/README.md). 초기 1.5m 배치, 재부팅 점검, Wi-Fi 접속 시험과 이전 반복 로그는 공유하지 않는다.

## 실제 코드와 현재 정책

실제 DW3000 ranging은 `firmware/uwb_multi_test/src/tag.cpp`, `anchor.cpp`다. `firmware/uwb_position_device` mock과 미구현 hardware adapter는 대상이 아니다. 실제 태그는 ESP32-D0WD-V3 + DW3000이며 마지막 현장 버전은 `uwb-capture-20261015.2`다. 앵커와 P4 AV 보드 펌웨어는 이번에 변경하지 않았다.

```dotenv
UWB_CALIBRATION_ENABLED=false
UWB_MEDIAN_ENABLED=true
UWB_MEDIAN_WINDOW=5
UWB_QUALITY_MODE=observe
UWB_SPEED_MODE=observe
```

보정값 파일은 보존하되 적용하지 않는다. 신호 임계값 제외·감량과 최대 속도 거부는 구현돼 있으나 기본은 관찰 모드다. 강제 적용하려면 각각 `enforce`로 설정하고 재시작한다. 임계값과 속도 기본값은 현장 검증되지 않은 시험 가정이다. 구형 `quality=0.95`와 WiFi.RSSI는 실제 UWB 품질로 해석하지 않는다.

## 처리 순서와 코드

프레임 검증·중복 제거 → 신호 품질 판별 → 거리 보정·중앙값 → 위치 계산 → 최대 속도 검사 → 좌표 중앙값/EMA/정지 처리 → 지도 제한 → 유효 위치·위험구역 갱신.

| 기능 | 파일과 핵심 동작 |
| --- | --- |
| 측정/진단 | `tag.cpp`, `uwb_diagnostics.h`, `uwb_measurement_snapshot.h`, `uwb_telemetry.h`: 부팅 세션+64bit cycle+8bit sequence, MCU uptime, 각 Response 직후 원시 CIA 복사. USB/Wi-Fi 동일 ID/스냅샷. |
| 공통 거리 처리 | `uwb_distance_filter.py`, `uwb_live_bridge.py`: 보정과 중앙값은 서버 한 곳에서 처리. USB 중복 보정/필터/과거 앵커 hold 제거. `distances_calibrated=true`는 서버 보정을 다시 적용하지 않음. |
| 신호 판별 | `uwb_quality_service.py`: 전체/첫 경로 전력·전력 차이·peak/FP 차이와 무효 상태 기록. enforce에서는 중앙값 전에 실제 제외 또는 감량. 누락은 정상으로 간주하지 않음. |
| 위치 검사 | `location_service.py`, `location_speed_service.py`: 기존 solver의 유효성 검사와 평활화 전 속도 검사. 후보와 화면 좌표를 분리. |
| 상태/로그 | `routers/uwb.py`, `uwb_log_service.py`, `serializers.py`, 모델/스키마, 프런트 타입/상세 화면: 통신 성공, 거리 사용, 계산 성공, 위치 수락과 마지막 유효 위치 나이 구분. DB 변경은 3개 상태 열의 추가 migration. |
| 전송 분리 | `uwb_delivery_policy.h`, `uwb_telemetry.h`: ranging과 USB/HTTP 작업 분리. DW3000 접근은 ranging 주체 한 곳만 수행. |

거리 이력 키는 조직·사이트·태그·앵커다. N=5, 샘플 TTL=3초, 프레임 최대 나이=5초, 긴 단절 초기화=15초, 상태 TTL=1시간, 최대 태그=1000이 기본이다. N 미만은 현재 유효 표본만으로 중앙값을 계산하며 사유/개수를 기록한다. 누락 앵커를 과거 값으로 대체하지 않는다. 신규 측정만 창을 갱신하고 같은 ID의 USB/Wi-Fi 중복, 역순, 이전 부팅, 잘못된 시각은 거부한다. 255→0 sequence 순환은 cycle/session으로 구분한다.

품질 enforce의 명확한 불량은 전력 차이와 경로 차이의 조합으로 판정한다. 잠정 경계는 power gap 6/12dB, 경로 차이 4/10 samples, 약한 RX -90dBm/FP -95dBm이며 약한 전력 하나만으로 NLOS를 단정하지 않는다. 제외 시 이력을 비우고 정상 3회·최소 0.6초를 확인해 복귀한다. 완전 제외는 `quality=0`과 별개이며 solver 입력에서 제거한다. 현재 observe에서는 이력·가중치에 영향 없다.

속도 기본은 `이동거리 > 3m/s × 같은 태그 측정 시각 차이 + 1m`다. 기준은 화면 정지 좌표와 별도로 마지막 검사 통과 후보를 보관한다. 최초/재부팅/긴 단절에는 일관된 3회·0.6초 재획득, 연속 거부 뒤에는 5회·2초 조건과 일관된 후보 3회를 확인한다. 적용 모드의 거부 후보는 좌표 필터와 위험구역 상태를 갱신하지 않는다. 거리 이력 수락과 위치 수락은 별개다. 상세 설정명과 조건은 `config.py` 및 `location_speed_service.py`를 확인한다.

서로 다른 유효 앵커가 3개 미만이거나 해가 수렴하지 않음/기하 불안정/잔차 과다이면 새 위치를 확정하지 않는다. 마지막 위치와 나이·사유를 반환한다. DS-TWR, 높이 보정, 새 위치 계산 알고리즘은 추가하지 않았다.

**서버 worker 1개만 지원한다.** 거리/품질 상태는 SQLite 트랜잭션으로 직렬화하지만 좌표 필터·속도·구역·파일 로그까지 다중 프로세스 일관성을 보장하지 않는다.

## 진단·전송·보존

[DW3000 계산 근거](UWB_MEASUREMENT_LOGGING.md). STS OFF, Ipatov, **앵커→태그 Response 수신 방향**만 수집한다. 앵커의 Poll 진단은 응답 예약 타이밍 영향 때문에 이번에 추가하지 않았다. 진단 `valid`는 계산 가능을 뜻하며 LOS나 정확한 거리 보장이 아니다.

수신 직후 다음 RX 전에 원시 진단을 복사한다. ranging 경로에서 HTTP/JSON/log10을 수행하지 않는다. 고정 크기 스냅샷이므로 전송 도중 다음 측정으로 값이 바뀌지 않는다.

USB 큐 8회차, HTTP 큐 4회차이며 포화 시 오래된 대기 회차를 버린다. HTTP는 최신 회차 우선, 원래 측정부터 1.5초가 지난 데이터의 새 요청/재시도 금지, 연결 timeout 300ms/읽기 500ms, 회차당 최대 2회·재시도 간격 200ms다. 새 측정이 있으면 옛 재시도보다 우선한다. 재시도 ID/시각/payload는 동일하다. Wi-Fi 재접속 간격은 10초다. USB는 로그 목적이라 별도 나이 만료 없이 용량만 제한한다.

이미 진행 중인 HTTP 호출의 전체 시간 상한은 보장하지 않는다. DNS/쓰기/느린 헤더와 실제 무선 장애에서 측정 주기 유지 검증이 남아 있다. `[UWB_DELIVERY]` 5초 집계로 성공·실패·폐기·측정 간격·비콘 재동기화를 확인한다. PC/서버 로그는 각 경로 10MiB×5파일, 보존 7일이며 먼저 용량 제한에 도달하면 더 일찍 지워진다. 실험 파일은 별도 보관한다.

## 실행과 검증

저장소 루트에서 가상환경 및 기존 프로젝트 의존성을 준비한다. 서버 DB는 기존 방식으로 초기화하고 실제 현장에 맞춰 지도/앵커/장치를 등록해야 한다. 공유 자료가 현장 설정을 대신 적용하지 않는다.

```powershell
# backend/.env에 위 정책을 설정. 실제 Wi-Fi 비밀번호/DB는 Git에 추가하지 않는다.
$env:OPERATION_MODE='hardware'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --workers 1
# 별도 터미널
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

```powershell
# 루트에서 USB 로그 전용; 실제 포트를 지정
.\.venv\Scripts\python.exe uwb_live_bridge.py --port COM6 --log-only --log-path logs/field.jsonl
# 펌웨어: firmware/uwb_multi_test에서 기존 PlatformIO 환경 사용
pio run -e tag
pio run -e tag -t upload --upload-port COM6
# Wi-Fi 없이 USB 전용 펌웨어
pio run -e tag-usb-log
# 백엔드 테스트
cd backend
..\.venv\Scripts\python.exe -m pytest tests -q --tb=short
```

태그 UART/bridge 기본 460800baud, 기존 앵커 115200baud. Wi-Fi 설정은 `wifi_secrets.example.h`를 참고해 무시되는 `wifi_secrets.h`에 로컬 작성하고 서버 URL은 태그에서 접근 가능한 PC LAN 주소를 사용한다. 기존 태그로 복원할 때는 로컬 검증된 flash 백업/manifest와 `scripts/restore_uwb_tag.ps1`을 사용한다. 백업은 비밀번호를 포함할 수 있어 공유하지 않는다. 다음 작업자의 장치에는 이 PC의 백업이 있다고 가정하지 않는다.

공유 직전 검증 결과는 [측정 자료 README](measurements/2026-10-15-comparison/README.md)에 기록한다. 펌웨어/프런트 소스는 앞서 빌드된 안정화 코드와 동일하며 이번 정리에서 변경하지 않았다. 실물 HTTP 장애·큐 포화·비콘 주기 유지, LOS/몸/벽별 판별 정확도, 이동 중 위치 정확도는 미검증이다.

## 다음 Codex 작업 시작문

> 이 브랜치의 docs/UWB_HANDOFF_2026-10-15.md와 docs/measurements/2026-10-15-comparison/README.md를 먼저 읽고 현재 브랜치/AGENTS.md를 확인해줘. 보정 OFF, median5, 품질/속도 observe 정책을 유지해줘. P4 기준은 722c9fd이며 이 브랜치는 P4 전체 통합본이 아니다. 현장 지도/DB/비밀번호를 Git에 올리지 마. 선택한 같은 입력 비교에서 수정본은 대략 중앙에 더 가까우나 표시 산포가 P4보다 크다. 지도 경계 고정, 정지 필터와 거리 편향을 구분해 원인을 먼저 분석하고, 임계값 제외나 추가 필터를 근거 없이 켜지 마. 실행 중 서버와 하드웨어는 확인 후 조작하고 정확도 개선을 과장하지 마. 요청 전에는 커밋/푸시/PR을 만들지 마.
