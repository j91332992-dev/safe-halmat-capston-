# 전체 프로젝트 A to Z 가이드

## 1. 프로젝트 목표

프로젝트명은 `esp32-smart-safety-system`입니다. 안전모에 장착한 ESP32-S3-CAM AV 장치와 ESP32 UWB DW3000 위치 장치가 카메라·음성·버튼·거리 데이터를 PC 서버로 보내고, FastAPI가 AI·위치·위험도를 통합하며 React 웹이 실시간 관제를 제공합니다.

최종 목표는 부품별 테스트 파일이 아니라 실제 하드웨어와 연결되는 하나의 통합 프로그램입니다.

## 2. 네 가이드 사용 순서

1. 이 문서로 일정, 역할, 통합 순서와 시연 완료 기준을 확인합니다.
2. `SOFTWARE_A_TO_Z_GUIDE.md`로 PC 환경과 서버·웹을 먼저 실행합니다.
3. `HARDWARE_A_TO_Z_GUIDE.md`로 전원·배선·안전모·UWB를 제작합니다.
4. `TEAM_PARTS_A_TO_Z_GUIDE.md`에서 팀원별 파일과 인수인계를 확인합니다.

## 3. 전체 시스템 구조

```text
안전모 AV 장치 ── JPEG/PCM/버튼/heartbeat ──┐
                                             ├─ FastAPI + SQLite
안전모 UWB 태그 ── 앵커 거리/품질 ──────────┘       │
                                                     ├─ YOLO/STT/intent
UWB 앵커 4개 ↔ 태그                                  ├─ 위치/구역/위험도
                                                     └─ WebSocket
                                                           │
                                                     React 관리자 웹
```

## 4. 팀 구성

| 담당 | 핵심 결과 |
|---|---|
| 비전 | OV5640 JPEG와 YOLO/dummy PPE·화재·연기 |
| 음성·AI | INMP441 WAV, STT/dummy, intent, MAX98357A 경고 |
| UWB | 태그·앵커 TWR, 서버 x/y, 필터와 confidence |
| 통합·웹 | DB, 위험도, 이벤트, 명령, WebSocket, 관리자 화면 |
| 전원·기구 | 배터리·충전·승압, 공통 GND, 절연과 안전모 장착 |
| 테스트·문서 | 설치, Git, 통합 시나리오, 로그와 시연 백업 |

자세한 파일 책임은 팀원 담당 파트 가이드를 따릅니다.

## 5. 0단계: 저장소 시작

```powershell
git init
git checkout -b main
git add .
git commit -m "feat: ESP32 스마트 안전모 1차 통합 시스템"
git remote add origin <GitHub 저장소 URL>
git push -u origin main
git checkout -b dev
git push -u origin dev
```

main을 보호하고 feature→dev→main PR 흐름을 사용합니다.

## 6. 1단계: PC 통합 프로그램 실행

```powershell
cd "C:\Users\조성준\OneDrive - pukyong.ac.kr\바탕 화면\한미르\esp32-smart-safety-system"
.\install_windows.bat
.\run_all.bat
```

`http://localhost:5173`에서 작업자, 앵커 4개, 위험구역, 위험도와 이벤트를 확인합니다. `/api/health`와 `/docs`도 엽니다.

첫 단계에서는 실제 하드웨어가 없어도 전체 데이터 흐름을 검증해야 합니다.

## 7. 2단계: Mock 기준선 고정

다음 시나리오를 모두 실행하고 결과를 기록합니다.

| 시나리오 | 기대 결과 |
|---|---|
| 정상 | 안전 위치, PPE 착용, 위험 0 |
| 위험구역 | 위치가 구역 안, 구역 이벤트, +30 |
| PPE 미착용 | 조끼 +10, 장갑 +5 |
| 화재 | +50, danger 이벤트 |
| 연기 | +40, danger 이벤트 |
| 비상 | 위험 100, emergency 이벤트 |
| 장치 오프라인 | offline 표시와 +10 |
| 음성 명령 | text→intent→응답/이벤트 |
| 버튼 triple | 즉시 100 |
| 관리자 경고 | 장치 command queued/delivered |

이 기준선이 깨진 상태에서 실제 하드웨어 개발을 시작하지 않습니다.

## 8. 3단계: 하드웨어 조사와 전원부

1. 정확한 ESP32-S3-CAM과 UWB 보드 리비전을 기록합니다.
2. 카메라·PSRAM·USB·SPI 핀을 회로도에서 확인합니다.
3. LiPo→TP4056→스위치→TPS61088을 제작합니다.
4. ESP32 연결 전 무부하 5.0V와 쇼트 여부를 측정합니다.
5. 모든 GND를 공통으로 설계합니다.
6. 실제 핀을 각 `config.h`에 기록합니다.

## 9. 4단계: 장치 등록과 heartbeat

AV 기능과 UWB ranging보다 먼저 두 장치가 실제 서버에 접속하게 합니다.

1. Wi-Fi SSID/PW와 PC IPv4를 입력합니다.
2. AV 최종 펌웨어를 업로드합니다.
3. `helmet-001-av` register/heartbeat를 확인합니다.
4. UWB 태그 최종 펌웨어를 업로드합니다.
5. `helmet-001-uwb` register/heartbeat를 확인합니다.
6. 웹 진단에서 online, RSSI, battery, component status를 봅니다.

이 단계에서 장치 ID와 API 계약을 고정합니다.

## 10. 5단계: AV 기능 통합

권장 순서:

1. OV5640 초기화와 JPEG 업로드
2. INMP441 I2S 초기화와 PCM/WAV 업로드
3. 버튼 single/double/triple/long
4. WebSocket 장치 명령
5. MAX98357A 경고음

배선은 한 번에 하나씩 추가할 수 있지만 확인은 항상 같은 최종 AV 펌웨어와 관리자 진단 화면에서 합니다.

## 11. 6단계: UWB 기능 통합

1. 앵커 4개에 고유 ID를 넣고 5V USB로 고정 전원을 공급합니다.
2. 현장 원점과 x/y/z를 측정해 서버에 등록합니다.
3. mock adapter 기준 거리 JSON과 서버 좌표를 확인합니다.
4. 실제 DW3000 라이브러리를 adapter 내부에 연결합니다.
5. 앵커별 거리 오차와 quality를 보정합니다.
6. 실제 이동, 지도 위치, confidence와 경로를 확인합니다.

## 12. 7단계: 위험도 통합

카메라 PPE/hazard, UWB 구역, 장치 online/battery, 버튼/음성 비상을 하나의 worker state에 합칩니다.

검증할 조합:

- 위험구역+PPE 미착용
- 화재+연기
- 낮은 위치 confidence
- 배터리 15% 이하
- 장치 오프라인
- 비상 100점 우선

점수와 화면의 근거 합계가 같아야 합니다.

## 13. 8단계: 안전모 장착

카메라는 전면, 마이크는 턱끈 근처, 스피커는 귀를 막지 않는 측면, 버튼은 장갑으로 누르기 쉬운 위치, UWB는 상단, 배터리는 후면 균형 위치에 둡니다.

충격 흡수재를 손상하지 않고 절연·완충 케이스와 비구조용 고정재를 사용합니다. 케이블이 얼굴·목에 닿거나 시야를 가리지 않게 합니다.

## 14. 9단계: 통합 시험

### 소프트웨어 시험

- backend pytest
- frontend production build
- 모든 REST API와 WebSocket
- SQLite 재시작 후 샘플/이벤트

### 하드웨어 시험

- 10분 이상 연속 동작
- 카메라/스피커 부하 순간 5V
- Wi-Fi 재연결과 heartbeat 복구
- 서버 종료 중 버튼 비상 로컬 경고
- UWB 이동/정지/경계 위치
- 배터리·승압기·앰프 발열

### 통합 시나리오

정상 이동→위험구역 진입→PPE 미착용→화재/연기→관리자 경고→음성/버튼 비상→장치 오프라인/복구 순서로 진행합니다.

## 15. 10단계: 최종 시연

1. 전날 배터리를 충전하고 예비 USB 전원과 케이블을 준비합니다.
2. PC 업데이트와 절전 모드를 끄고 로컬 모델/설치 파일을 확인합니다.
3. 앵커가 움직이지 않았는지 좌표를 재확인합니다.
4. 시연 30분 전 서버·웹·시뮬레이터를 실행합니다.
5. 실제 장치 heartbeat와 정상 상태로 시작합니다.
6. 지도 이동, 위험구역, PPE/화재 모사, 경고, 비상을 순서대로 보여줍니다.

RGB 조명과 가습기는 사람·전자 장치에 안전한 거리에서 사용합니다.

## 16. 백업 플랜

| 실패 | 백업 |
|---|---|
| YOLO 모델 | dummy detection으로 같은 위험 흐름 시연 |
| STT 모델 | mock-command로 intent/경고 시연 |
| DW3000 | simulator 또는 `uwb_mock.cpp`로 동일 API 시연 |
| Wi-Fi | 전용 2.4GHz 공유기/핫스팟 |
| PC | 저장소와 모델을 복제한 예비 PC/USB |
| 안전모 전원 | 절연 보관한 예비 배터리/USB 전원, 현장 병렬 연결 금지 |

백업은 기능을 숨기는 것이 아니라 실제 구현 대기 부분을 명확히 표시하고 동일한 최종 시스템 계약을 보여주는 방식입니다.

## 17. 주차별 권장 일정

| 주차 | 목표 |
|---|---|
| 1주차 | 저장소, mock 서버/웹, API와 역할 고정 |
| 2주차 | 전원부, 보드 조사, 실제 register/heartbeat |
| 3주차 | 카메라·마이크·스피커·버튼 통합 |
| 4주차 | UWB 앵커/태그, 좌표와 필터 |
| 5주차 | 위험도, 안전모 장착, 장시간 시험 |
| 6주차 | 실제 AI 모델, 통합 회귀, 시연과 백업 |

## 18. 매일 작업 방식

1. dev 최신 상태를 가져옵니다.
2. 담당 feature 브랜치에서 한 책임만 수정합니다.
3. mock 기준선을 먼저 확인합니다.
4. 실제 구현과 diagnostic log를 추가합니다.
5. 담당 단위 테스트와 전체 통합 시나리오를 실행합니다.
6. 로그·화면·버전을 PR에 첨부합니다.
7. dev 병합 후 다른 팀 기능이 깨지지 않았는지 확인합니다.

## 19. AI 도구에 제공할 정보

- 정확한 목표와 수정할 파일
- 보드/리비전, 라이브러리와 도구 버전
- 실제 핀과 전압
- 재현 순서와 기대/실제 결과
- 서버 traceback/HTTP 응답
- 브라우저 Console/Network/WebSocket
- ESP32 부팅부터 오류 후 10초까지 시리얼
- 진단 summary/device JSON
- 바꾸면 안 되는 API/ID/mock/diagnostic 계약

## 20. 프로젝트 완료 조건

- `run_all.bat`으로 백엔드·프론트·시뮬레이터 실행
- 지도에 작업자·앵커 4개·위험구역 표시
- 실제/Mock 입력이 같은 API와 상태 구조 사용
- 구역·PPE·화재·연기·비상에 따라 위험도와 근거 갱신
- 관리자 경고가 안전모에 전달
- 장치·카메라·음성·버튼·UWB 상태를 최종 진단 화면에서 확인
- 전원·배선·안전모 장착 안전 확인
- pytest, 프론트 build와 통합 시나리오 통과
- 네 A to Z 가이드와 현재 코드가 일치
