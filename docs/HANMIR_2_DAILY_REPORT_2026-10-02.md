# HANMIR 2.0 — 2026-10-02 전체 작업 정리 및 인계

작성일: 2026-10-02 (한국시간)

대상 저장소: [j91332992-dev/safe-halmat-capston-](https://github.com/j91332992-dev/safe-halmat-capston-)

작업 브랜치: `feature/mobile-safety-app-20261001`

오늘 변경 전 기준 커밋: `9c2cd65` — 현재/P4 하드웨어 배선 문서 추가.

**이 브랜치는 기존 모바일 관제 앱에 HANMIR 2.0의 P4 전환 준비, 음성 경로 보완, 영상 통신 준비 코드를 추가한 작업 브랜치다. P4 펌웨어는 빌드·실물 검증 전이며, 모든 기능의 이식이 끝난 배포판이 아니다.** 아래에는 실제 작성된 코드, 설계만 있는 항목, 추가 구현과 검증이 필요한 항목을 구분했다.

## 팀원 전달용 작업 요청 — 아래 내용을 복사해서 사용

> HANMIR 2.0의 P4 하드웨어 재설계와 최종 배선표가 준비됐습니다. 이 저장소의 `feature/mobile-safety-app-20261001` 브랜치와 이 MD, `HARDWARE_REDESIGN_ESP32P4.md`를 먼저 확인하고, 기존 S3 기능과 서버 구조를 유지하면서 P4용 펌웨어·통신·카메라·음성·AI Agent까지 실제 코드로 이어서 업데이트해 주세요. 문서만 다시 작성하지 말고 미완료 항목을 구현하고, 빌드와 테스트 결과를 기록해 주세요.
>
> 우선순위는 ① P4 프로젝트를 현재 ESP-IDF로 빌드 가능하게 정리하고 보드 설정/핀 충돌을 검증하는 것, ② DFR1172 내장 C6 연결·복구와 heartbeat·명령 채널을 완성하는 것, ③ OV5647 CSI/ISP/JPEG를 붙여 HTTP 기준선과 영상 WebSocket을 비교하는 것, ④ INMP441·잡음 제거·`투투스`/무호출어 긴급 명령·STT·TTS를 연결하는 것, ⑤ AI Agent가 단순 조회/규칙 계산/LLM 설명을 분리하고 실제 서버 데이터 Tool을 쓰게 정리하는 것입니다. MAX17048, MAX98357A, BNO085, UWB 연동도 배선표 기준으로 단계적으로 반영해 주세요.
>
> S3 펌웨어를 덮어쓰거나 P4 미검증 GPIO·센서 설정을 확정값으로 하드코딩하지 마세요. P4에서 아직 동작하지 않는 기능은 상태를 드러내고, 기능별 수정 파일·빌드/시험 결과·남은 실물 확인 항목을 이 MD에 갱신한 뒤 같은 작업 브랜치에 커밋·푸시해 주세요.

### 이어받을 시작점

- 브랜치: `feature/mobile-safety-app-20261001` — 오늘 P4 준비 코드, 서버·PWA 변경이 올라가 있다. 새 작업은 이 브랜치의 최신 원격 커밋에서 시작한다.
- 기준 하드웨어: [최종 P4 배선표](HARDWARE_REDESIGN_ESP32P4.md)와 그 안의 전원·예약 핀 표. S3 배선표는 S3 회귀 비교용이다.
- 구현 시작 파일: [P4 통합 프로젝트](../firmware/helmet_p4/README.md)의 모듈 목록과 현재 제한을 읽고, `camera_source.c` 등 명시된 미구현 지점부터 코드로 완성한다.
- 통신 계약: 이 문서의 **7절** P4 영상 WebSocket 프레임 포맷과 현재 백엔드 `backend/app/routers/camera.py`를 함께 확인한다. 서버와 펌웨어 버전이 함께 맞도록 수정한다.
- AI Agent/음성 기준: 이 문서의 **4절**, [음성 준비 상태](HANMIR_2_VOICE_PREP_2026-10-02.md), 기존 `backend/app/services/assistant_service.py`, `speech_service.py`, `wake_word_service.py`, `backend/app/routers/audio.py`를 확인한다.
- 업데이트 방식: 현재 코드 구조와 실제 서버 API를 먼저 대조한다. 문서의 제안이나 오래된 수치는 확인 없이 구현 요구사항으로 단정하지 말고, 변경 전후 동작과 결과를 기록한다.

### 작업 완료 기준

| 우선순위 | 완료됐다고 볼 수 있는 결과 |
|---|---|
| P0 — 펌웨어 기반 | 고정한 ESP-IDF/컴포넌트 조합으로 P4 빌드 성공. DFR1172 C6·flash/PSRAM 설정을 기록. 최종 배선 후보 중 검증된 핀만 켜고 예약·중복 검사가 동작 |
| P1 — 네트워크/제어 | AP·서버 재시작 후 Wi-Fi 복구, 장치 재등록, heartbeat, 별도 명령 WS와 스피커 ACK 확인 |
| P1 — 카메라/전송 | 실 OV5647 캡처·ISP·JPEG가 동작. 같은 장면으로 POST/WS를 비교해 수신 FPS·지연·드롭 측정. 원본 미리보기와 YOLO 분석 frame ID를 구분 |
| P1 — 음성 안전 경로 | 실 INMP441 PCM·NS/VAD·STT·응답·TTS를 확인. `투투스`와 `살려주세요`/`불이야`를 분리 측정하고 긴급어 미탐·오탐·지연 기록. 무선·카메라 부하 동시 확인 |
| P2 — AI Agent | 현재 서버 데이터/API를 읽는 Tool 목록과 입력/출력 검증 구현. DB 직접 응답, 코드 규칙 계산, LLM 설명을 분리. 확인 불가 값을 추측하지 않는 동작과 음성용 짧은 응답 확인 |
| P2 — 센서/장기 안정성 | MAX17048 SOC 비교, MAX98357A 재생, BNO085 보고 해석/낙상 로직, UWB 동시 통신, 장시간 부하 및 전원/재연결 시험 결과 기록 |
| 게시/인수 | 파일별 변경, 재현 가능한 빌드·테스트 명령과 결과, 실물 시험 조건·측정값·남은 제한을 MD에 갱신하고 같은 작업 브랜치에 커밋·푸시 |

실물 부품이 없으면 해당 단계를 **대기**로 기록하고, 빌드 가능한 코드와 시뮬레이션·서버 경로처럼 독립적으로 끝낼 수 있는 작업은 진행한다. 소스에만 존재하는 설정, 테스트 통과, 실물 검증을 서로 바꿔 말하지 않는다.

## 1. 오늘의 목적과 결정

기존 HANMIR의 FastAPI·YOLO·STT·TTS·DB·React/PWA 구조를 활용하면서 ESP32-S3 AV 장치를 DFR1172 ESP32-P4로 옮길 준비를 했다. 사용자가 가장 우선한 문제는 카메라 끊김과 낮은 실효 프레임률, 헬멧 영상의 YOLO 인식 저하, `투투스` 호출 실패와 음성 응답 지연이다.

오늘 정한 방향은 다음과 같다.

1. AV 주 제어기는 P4를 사용하며 무선은 보드 내장 C6를 이용한다. 외장 C5와 ESP-NOW는 초기 구성에 넣지 않는다.
2. UWB는 기존 독립 ESP32 태그가 자체 Wi-Fi로 서버에 전송한다. P4에는 UWB 데이터선을 연결하지 않는다.
3. 카메라 촬영, 영상 송신, 마이크 처리, 음성 업로드, 서버 명령 처리를 나눈다. 느린 영상 송신이 음성 캡처를 직접 기다리게 하는 구조를 피한다.
4. 일반 영상은 최신성 우선으로 대기 프레임 한 장만 유지한다. 서버의 원본 미리보기와 YOLO 분석 결과는 별도로 표시한다.
5. 영상 전송은 기존 HTTP multipart POST로 비교할 수 있게 하고, 바이너리 WebSocket 경로도 준비한다. H.264/UDP/RTP는 이번 구현에 포함하지 않았다.
6. 일반 조회·명령은 규칙 응답을 우선한다. 복합 설명만 LLM 경로로 보낸다. API 모델은 설정으로 바꿀 수 있게 유지한다.
7. 실제 검증되지 않은 GPIO는 기본 `-1`로 둔다. 배선 후보를 실제 검증 완료값처럼 취급하지 않는다.

## 2. 현재 상태 한눈에 보기

| 분야 | 오늘 확보한 것 | 남은 것 |
|---|---|---|
| 문서 | 음성 준비, 통신 개편, 오늘 전체 인계 문서 | 실물 시험 결과·최종 설정 기록 |
| P4 Wi-Fi | ESP-Hosted/remote Wi-Fi 의존성, STA 시작·재연결 코드 | DFR1172 내부 SDIO 설정과 C6 펌웨어 호환 확인 |
| P4 상태 관리 | 장치 등록, heartbeat, 연결 뒤 재등록 | 실제 AP/서버 재시작 시험 |
| P4 영상 송신 | 최신 1장 큐, POST/WS 선택, 바이너리 프레임 번호 | 실제 캡처 프레임 연결·전송 지연 측정 |
| OV5647 캡처 | 모듈과 호출 계약 | **CSI·ISP·JPEG 캡처 구현 미완료** |
| 음성 | AFE NS/VAD, 300ms pre-roll, WAV 업로드, 서버 시간 계측 | 마이크 실측·맞춤 WakeNet 모델·인식률 평가 |
| 스피커 | I2S1 톤·16kHz WAV 재생, 명령 WS | 실물 음량·끊김·재생 완료·중단 명령 검증 |
| 배터리 | MAX17048 I2C1 SOC 읽기·heartbeat | 실물 전압/SOC 비교와 전원 연결 확인 |
| IMU·낙상 | 설정 자리와 상태 함수 | **BNO085 SHTP 수신·낙상 판정 미구현** |
| 통화 | 기존 S3/서버 통화 구조 유지 | **P4 양방향 PCM 통화 미이식** |
| 서버·PWA | 새 영상 수신·원본 API·원본/분석 분리 화면 | 실제 JPEG·복수 장치·동시 음성 부하 시험 |
| 모바일 패키지 | React/PWA 소스 수정 | **IPA/APK 재빌드·서명·배포 미실행** |

## 3. 기존 S3 통신과 YOLO 문제 분석

기존 S3는 OV5640 DVP에서 VGA JPEG를 얻고 매 프레임 `HTTPClient`로 multipart POST를 보낸다. 전체 요청 버퍼 복사와 동기 전송을 수행하므로 촬영·복사·송신·서버 응답을 합친 시간이 목표 주기보다 길면 설정 FPS에 도달하지 못한다.

서버는 이미 수신 요청을 YOLO 완료까지 기다리게 하지 않고 `202`를 반환하며, 대기 프레임 한 장을 유지한다. 따라서 모든 병목을 HTTP 프로토콜 하나로 설명할 수 없다. 서버 추론 시간, 파일 입출력, 무선 경합, 영상 품질, 화면 갱신 주기를 각각 봐야 한다.

이전 통신 계획에 인용한 과거 기록은 서버 수신 약 5.27FPS, 분석 약 2.40FPS, JPEG 평균 16.77KB, CPU 최대 100%다. **오늘 재측정한 결과가 아니며, P4의 예상 성능도 아니다.** 원자료와 조건이 함께 확인되지 않는 수치는 합격 결과로 발표하지 않는다.

PC 카메라에서 같은 YOLO 모델이 잘 되고 헬멧 영상에서 실패하는 현상은 다음을 나누어 확인해야 한다.

- 렌즈 초점, 노출, 흔들림, 압축, 색 처리, 작업자 거리와 작은 PPE의 픽셀 수.
- 서버에서 실제로 쓰는 모델 파일·입력 크기·confidence와 PC 시험 조건의 차이.
- 사람 ROI 추가 분석 실행 여부와 추론 처리량.
- 촬영·수신·분석·표시 FPS의 차이 및 오래된 결과를 보고 있는지 여부.

오늘 YOLO 모델을 교체하거나 재학습하지 않았다. 원본을 따로 볼 수 있게 하여 다음 시험에서 카메라 품질과 통신 지연을 구분할 준비를 했다.

## 4. AI Agent·STT·긴급어 서버 변경

### 4.1 현재 논리

음성 업로드 → STT → 호출어/긴급어 판정 → 중복 실행 제어 → intent 분류 → 규칙 또는 LLM 응답 → TTS → 장치 명령 순서다. 위험 상태는 외부 AI/TTS 응답 대기 전에 DB에 저장하는 기존 구조를 활용한다.

`assistant_service.py`의 `FAST_INTENTS`는 관리자 호출, 상태·위치·위험도 조회, 도움·비상·화재 신고, 대피 안내, 경고 반복이다. 이 경로는 규칙 응답을 사용한다. 기타 요청은 API 키와 설정이 있을 때 LLM을 사용하고 실패하면 기본 응답으로 돌아간다.

사용자가 제안했던 `get_worker_heading()`, `get_worker_battery()`, `get_nearest_exit()` 같은 전체 Tool Calling 체계의 재작성은 오늘 완료하지 않았다. 현재 intent 처리와 서비스 함수를 미래 Tool 설계와 혼동하지 않는다. 센서 값의 유효시각·확인 불가 처리도 추가 정리가 필요하다.

### 4.2 소스 기본 설정

| 항목 | 소스 기본값 | 주의 |
|---|---|---|
| STT | `gpt-4o-mini-transcribe` | `.env`의 `STT_MODEL`이 우선 |
| STT 언어 | `ko` | 모델별 언어 인자 처리 분기 포함 |
| STT timeout | 10초 | SDK 자동 재시도 0회 |
| LLM 후보 | `gpt-6-luna` | 실제 API 사용 가능 여부·품질·비용 실험 미실행 |
| LLM timeout | 5초 | SDK 자동 재시도 0회 |
| LLM 출력 상한 | 80토큰 | 후보 모델일 때 reasoning `none` 설정 |
| TTS | Edge TTS `ko-KR-SunHiNeural` | 서버에서 16kHz/16bit/mono WAV 변환 |

위 표는 **현재 코드에 기록한 기본값**을 설명한다. 유료 API 호출 성공, 응답 속도, 모델별 비용 우위가 오늘 검증되었다는 뜻이 아니다. 과거 음성 준비 문서에 적힌 가격·모델 일정은 API 전환 시 공식 문서와 계정 사용 가능 모델을 다시 확인해야 한다.

### 4.3 오늘 수정한 동작

- `POST /api/audio/upload`에 `wake_detected` Form 값을 추가했다. 기본은 `false`라 기존 S3 경로를 유지한다.
- `wake_detected=true`이면 호출어가 없는 명령 WAV로 STT를 요청하며 서버 텍스트 호출어 검사를 건너뛴다. 빈 전사는 명령으로 실행하지 않는다. 이 플래그를 보내는 장치의 검증된 모델과 신뢰 경계가 필요하다. 현재 P4 통합 앱은 이 플래그를 보내지 않는다.
- `불이야`, `불이났어`, `불났어`를 긴급 화재 표현에 추가했다. 기존 `살려주세요`, `비상상황`, `화재발생` 경로도 유지한다.
- 명확한 긴급 문구를 `sound_db < 80`이라는 이유만으로 취소하던 조건을 제거했다.
- 저장·STT·답변 생성·TTS·서버 전체 처리의 `timings_ms`를 기록한다. 이는 서버 내부 시간이며 마이크 발화 시작부터 재생까지의 전체 지연은 아니다.
- 실패한 STT를 가짜 문장으로 대체하지 않도록 실제 동작과 로그 설명을 맞췄다.

## 5. P4 마이크 실험 프로젝트

`firmware/helmet_p4_voice_lab`은 통합 앱과 별개의 마이크 단독 실험용 ESP-IDF 프로젝트다.

- 외장 INMP441의 32bit I2S 슬롯을 받아 상위 16bit PCM으로 변환한다.
- ESP-SR `2.5.5`를 의존성으로 고정했다. WebRTC 잡음 제거와 VAD를 설정한다.
- WakeNet은 기본 비활성이며, 모델이 있는 경우 감지 이벤트만 로그로 남긴다.
- AFE 출력 PCM을 base64 콘솔 라인으로 보내는 진단 옵션과 `capture_serial.py` WAV 저장 도구를 추가했다.
- PCM 콘솔 출력은 처리시간에 영향을 주므로 실제 호출 지연 시험에서는 끈다.
- 이 프로젝트 자체에는 C6 업로드·카메라·통화 통합이 없다. 실제 통합은 별도 `helmet_p4` 프로젝트에서 진행한다.

사용자가 기억하는 호출 성공률 60~70%는 체감 추정이다. 맞춤 한국어 `투투스` 모델이나 비상어 모델은 확보되지 않았으며, 오늘 인식률 개선 비율을 측정하지 않았다.

## 6. P4 통합 펌웨어 파일별 역할

| 파일 (`firmware/helmet_p4/` 기준) | 역할 |
|---|---|
| `CMakeLists.txt`, `main/CMakeLists.txt` | 독립 ESP-IDF 앱과 모듈 빌드 구성 |
| `main/idf_component.yml` | ESP-Hosted, remote Wi-Fi, WebSocket, ESP-SR 의존성 |
| `sdkconfig.defaults`, `partitions.csv` | 16MB flash 기준 설정, factory/model 파티션, PSRAM |
| `main/Kconfig.projbuild` | 네트워크·식별자·토큰·GPIO·음성·영상 모드 설정 |
| `main/hanmir.h` | 모듈 사이 함수 계약 |
| `main/app_main.c` | NVS·핀 검사·센서·네트워크·명령·음성 시작 |
| `main/pin_guard.c` | 문서의 예약 GPIO와 외부 모듈 중복 GPIO 검사 |
| `main/network.c` | STA 시작, IP 취득, 끊김 후 Wi-Fi 연결 시도 |
| `main/api_client.c` | 등록/heartbeat, WAV multipart 업로드, 스피커 결과 보고 |
| `main/camera_transport.c` | JPEG 최신 슬롯, HTTP 비교 모드, 바이너리 WS 전송 |
| `main/camera_source.c` | OV5647 캡처 연결 자리. 현재 `ESP_ERR_NOT_SUPPORTED` 반환 |
| `main/voice.c` | I2S RX→AFE→VAD/pre-roll→WAV 큐→서버 업로드 |
| `main/command_client.c` | 명령 WS, 명령 큐, 톤/경보/TTS 실행 |
| `main/speaker.c` | I2S TX, 톤 생성, 서버 WAV 다운로드·재생 |
| `main/sensors.c` | MAX17048 SOC 읽기. IMU ready는 현재 false |
| `README.md` | 설정·미완료 범위·실물 도착 후 연결 순서 |

### 6.1 음성의 실제 경계

통합 앱은 16kHz PCM, 300ms pre-roll, 500ms 종료 무음, 최대 5초 클립을 사용한다. 업로드 큐는 3개이고 클립당 최대 3회 전송을 시도한다. 스피커 재생 중에는 마이크 명령 수집을 억제하여 자기 음성의 재인식을 줄인다. 이것은 AEC가 아니며, 스피커가 말하는 동안 작업자의 긴급 발화도 놓칠 수 있다.

현재는 일반 VAD 구간도 서버 STT로 보낼 수 있으므로 상시 운영 시 API 비용·오인 호출을 측정해야 한다. 검증된 로컬 호출어/긴급어 모델이 준비된 저비용 완성 경로는 아직 아니다. 전원 차단을 견디는 긴급 큐도 없다.

### 6.2 통신의 실제 경계

영상·음성·명령은 별도 작업과 연결을 사용하지만 같은 P4 메모리·C6·AP를 공유한다. 작업 분리만으로 긴급 트래픽의 전송 우선순위나 실시간 응답이 보장되지 않는다. 지금은 고정 재연결 간격과 라이브러리 재연결 기능을 사용한다. 지수 백오프·혼잡에 따른 FPS 조절·ACK 기반 송신 창 제어·전송 시간 분포 계측은 추가 구현 대상이다.

## 7. 서버 영상 프로토콜과 PWA

### 7.1 기존 HTTP 경로

`POST /api/camera/frame`을 유지하고 선택적인 `frame_id`를 받도록 했다. 수신 원본을 메모리 미리보기에도 남긴다. P4 메뉴의 `HANMIR_CAMERA_HTTP_BASELINE`을 켜면 이 경로로 보낸다.

### 7.2 신규 바이너리 WebSocket

경로는 `/api/camera/stream/{device_id}?worker_id=...&helmet_id=...`다. 서버 `CAMERA_INGEST_TOKEN`과 일치하는 `X-Hanmir-Camera-Token` 헤더가 있어야 한다. 토큰은 비워 두면 신규 WS가 거부된다. 장치가 등록되어 있고 해당 작업자와 연결되어 있어야 한다.

| 오프셋 | 길이 | 필드 |
|---|---:|---|
| 0 | 4바이트 | ASCII `HMR2` |
| 4 | 8바이트 | big endian uint64 `frame_id` |
| 12 | 2바이트 | big endian uint16 width |
| 14 | 2바이트 | big endian uint16 height |
| 16 | 가변 | JPEG 원본 |

한 WebSocket binary message에 한 프레임을 보낸다. 서버는 길이·표식·양수 해상도 범위·연결 내 프레임 번호 증가·JPEG 시작/끝 표식을 검사한다. 실제 JPEG 디코드와 헤더 해상도 일치까지 검증하는 코드는 아직 없다.

최초 및 8프레임마다 수신 frame ID·분석 큐 깊이·대기 교체 여부를 ACK로 보낸다. 현재 P4는 이 ACK를 이용한 적응 제어를 구현하지 않았다. YOLO 큐는 기존 전역 1개를 사용하므로 여러 헬멧의 공정한 분석 스케줄링은 추가 과제다.

### 7.3 화면

- `/api/camera/{id}/live`: 원본 수신 여부, frame ID, 서버 수신 후 경과시간.
- `/api/camera/{id}/live/image`: 최신 원본 JPEG.
- 기존 `/latest`, `/latest/image`: 최근 YOLO 분석 데이터·이미지.
- `CameraMonitor.tsx`는 원본 상태를 500ms 간격으로 확인하고 3초 이상 새 프레임이 없으면 영상 정지로 표시한다. 이는 고FPS 스트리밍 플레이어 구현이 아니다.
- YOLO processor 상태의 목표 FPS 표시를 실제 평상시 분석 간격에 맞춰 수정했다.

## 8. 하드웨어 기준

최우선 P4 기준 문서는 [2026-10-01 최종 배선표](HARDWARE_REDESIGN_ESP32P4.md)다. 기존 S3 배선은 [현재 하드웨어 문서](HARDWARE_WIRING_CURRENT_2026-09-29.md)를 따른다.

| 장치 | 사용자 최종 배선 후보 | 현재 코드 |
|---|---|---|
| INMP441 | BCLK31 / WS34 / DATA36 | 기본 -1, 실물 확인 후 입력 |
| MAX98357A | BCLK20 / WS21 / DIN22 | 기본 -1, 실물 확인 후 입력 |
| MAX17048 | SDA33 / SCL32, I2C1, 0x36 | 기본 -1, 유효 SOC만 전송 |
| BNO085 | P4 RX23 / TX51, 표준 UART | 기본 -1, SHTP/낙상 미구현 |
| OV5647 | CSI FPC, SCCB SDA7/SCL8 | 실물 캡처 드라이버 미연결 |
| UWB | 공통 전원, P4 데이터선 없음 | 기존 독립 경로 유지 |

카메라와 MAX17048의 주소가 모두 0x36이어도 별도 버스를 사용한다. 핀 검사 코드는 문서상 예약 자원과 중복 할당을 잡는 수준이며, 실제 패드의 전기 특성·출력 가능 여부·SDIO 설정까지 보장하지 않는다. 전원·스위치·GND 조건은 하드웨어 배선 문서의 확인 순서를 따른다.

## 9. 진단 도구와 재현 절차

`backend/tools/compare_stt.py`는 CSV의 `file,reference`에 적힌 동일 WAV를 선택한 전사 모델에 보내 CER, 요청 지연, 추정 비용을 CSV로 저장한다. 이 도구는 명시적으로 실행할 때 유료 API를 호출한다. API 실험은 이번 업로드 과정에서 실행하지 않았다. 비용 상수는 청구 결과가 아니며 최신 단가와 비교해야 한다.

```powershell
# 마이크 단독 PCM 수집: 보드 연결과 메뉴 설정 후 실행
python firmware/helmet_p4_voice_lab/capture_serial.py --port COM12 --seconds 5 --out recordings/quiet_01.wav

# 유료 STT 비교: 실제 키와 평가용 WAV를 사용자가 준비한 후 실행
python backend/tools/compare_stt.py recordings/manifest.csv --out recordings/stt_result.csv
```

## 10. 변경 파일 범위

- 서버 설정: `backend/.env.example`, `backend/app/config.py`.
- 음성 서버: `routers/audio.py`, `services/assistant_service.py`, `audio_service.py`, `speech_service.py`, `whisper_service.py`.
- 영상 서버: `routers/camera.py`, `services/camera_service.py`.
- 프런트엔드: `src/components/CameraMonitor.tsx`, `src/services/api.ts`, `src/styles.css`.
- 음성 회귀 검사: `backend/tests/test_wake_word.py`, `backend/tests/test_p4_voice_upload.py`.
- 영상 회귀 검사: `backend/tests/test_p4_camera_stream.py` — 토큰 거부, 정상 프레임 ACK/원본, 중복·잘못된 헤더 거부, S3 multipart 호환 5건.
- 진단 도구: `backend/tools/compare_stt.py`, `firmware/helmet_p4_voice_lab/capture_serial.py`.
- 펌웨어: `firmware/helmet_p4/` 및 `firmware/helmet_p4_voice_lab/`의 소스·설정·README 전체.
- 문서: 이 문서, [음성 준비 상태](HANMIR_2_VOICE_PREP_2026-10-02.md), [통신 개편 계획](HANMIR_2_P4_COMMUNICATION_PLAN_2026-10-02.md), 저장소 README.
- Git 제외 규칙: 실제 `.env`, 생성된 P4 sdkconfig·빌드·다운로드 컴포넌트가 업로드되지 않도록 관리.

## 11. 검증 결과

| 검사 | 결과 | 범위와 제한 |
|---|---|---|
| 프런트엔드 `npm run build` | 성공 | TypeScript 및 Vite production build. 브라우저 실사용·IPA 빌드 결과는 아님 |
| 음성/에이전트 관련 pytest | **21개 통과** | 호출어, 로컬 wake 플래그, 조용한 화재 신고, 실행 gate, safety agent |
| 신규 영상 수신 pytest | **5개 통과** | 토큰 인증, ACK·원본 제공, 중복/헤더 오류 거부, 기존 S3 POST. 실제 JPEG 디코드·YOLO 추론은 실행하지 않음 |
| `git diff --check` | 성공 | 패치 공백/형식 오류 검사 |
| P4 ESP-IDF build | 미실행 | 현재 PC PATH에 `idf.py` 없음. firmware 컴파일 성공을 확인하지 못함 |
| 실물 마이크·카메라·무선·센서 | 미실행 | P4 보드 도착 전 |
| 유료 STT/LLM A/B, 인식률·지연 | 미실행 | 키·음성 원자료·동일 조건 실험 필요 |
| IPA/APK 재빌드·서명·설치 | 미실행 | 이번 변경은 앱 소스와 웹 build까지 |

검사는 저장소 내부 `.venv`에 `backend/requirements.txt`, 프런트엔드에 `npm ci`로 설치한 환경에서 실행했다. 실제 API 호출을 막기 위해 테스트 프로세스의 `OPENAI_API_KEY`를 비우고 `USE_EDGE_TTS=false`, `YOLO_ENABLED=false`를 설정했다. 테스트 DB는 기존 pytest fixture의 임시 DB를 사용했다. 기존 애플리케이션 `.env`는 변경하지 않았다.

실행 명령:

```powershell
# backend 폴더에서, 위 테스트 전용 환경변수 설정 후
..\.venv\Scripts\python.exe -m pytest tests/test_wake_word.py tests/test_p4_voice_upload.py tests/test_voice_execution_gate.py tests/test_safety_agent_service.py -q
..\.venv\Scripts\python.exe -m pytest tests/test_p4_camera_stream.py -q

# frontend 폴더에서
npm.cmd run build
```

의존성의 Starlette/httpx 사용 방식 및 기존 `datetime.utcnow()` 코드에서 deprecation 경고가 나왔다. 이번 지정 테스트 실패는 없었으며, 전체 서버 테스트 전체를 통과했다고 주장하지 않는다. `.venv`, `node_modules`, 생성된 `dist`, 실제 키·녹음·DB는 Git 업로드 대상에서 제외한다.

## 12. 실물 도착 후 진행 순서

1. ESP-IDF 환경을 설치하고 컴포넌트 의존성을 해결한다. `idf.py set-target esp32p4`, `menuconfig`, `build` 단계에서 드라이버 API·버전 호환성을 먼저 확인한다. 현재 일부 의존성은 버전 범위가 열려 있어 성공한 버전과 lockfile 기록이 필요하다.
2. DFR1172의 실제 flash/PSRAM, 내장 C6 출고 펌웨어, 내부 SDIO 설정을 확인한다. Wi-Fi만 켜서 IP·등록·heartbeat와 AP 복구를 확인한다.
3. MAX17048를 별도 I2C1에서 확인하고 SOC/전압을 비교한다.
4. 마이크 단독 실험 앱으로 신호 크기·채널·잡음 제거 전후를 확인한다. 이후 통합 앱에서 STT·긴급어·TTS 경로를 확인한다.
5. OV5647 CSI/ISP/JPEG를 단독 구동한 뒤 `hanmir_camera_submit_jpeg()`에 연결한다. POST 기준선과 WS 전송을 같은 JPEG 조건으로 비교한다.
6. PC 카메라·S3·P4 원본의 화질을 비교하고 동일 모델로 추론한다. 수신 FPS, 분석 FPS, 화면 최근성, PPE 미탐·오경보를 각각 기록한다.
7. P4 통화, BNO085 SHTP, 버튼, AEC와 긴급 영속 큐를 구현·검증한다. 미지원 명령과 실제 지원 상태를 UI/heartbeat에 맞춘다.
8. 장시간 동시 부하, AP 차단, 서버 재시작, 전원 재부팅을 확인한 뒤 운영 펌웨어와 모바일 패키지를 빌드한다.

## 13. GitHub에서 보는 방법

이 브랜치의 README 상단에서 오늘 작업 문서와 P4 통합 앱으로 들어갈 수 있다. 기존 모바일 앱 변경 위에 오늘 소스를 추가하여 이력으로 남긴다. 커밋 제목에 날짜와 P4/음성/통신 준비 범위를 명시한다. `main` 병합과 배포 완료를 의미하지 않는다.
