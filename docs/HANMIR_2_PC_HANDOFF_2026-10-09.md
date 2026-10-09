# HANMIR 2.0 — 다른 PC 인수인계 및 현재 진행상황

작성일: 2026-10-09 / 마지막 실물 확인: 같은 날 13:10 KST 부근.

이 문서는 다른 컴퓨터·다른 담당자가 현재 작업을 이어가기 위한 시작 문서다. 아래 상태는 확인 시점의 기록이며 장치가 계속 온라인이라는 뜻은 아니다. 비밀번호·API 키·장치 토큰은 포함하지 않았다.

## 1. 먼저 알아야 할 현재 상황

**P4 실물 업로드와 기본 서버 연결까지 완료했다.** 카메라 원본 전송, 서버 YOLO 추론, 배터리 읽기, 음성 처리 초기화, 명령 수신·스피커 재생 완료 보고를 확인했다. 독립 UWB 태그도 서버 주소를 고쳐 업로드했으며 앵커 4개 거리 수신과 서버 위치 갱신을 확인했다.

**남은 우선 작업은 UWB 실제 좌표 등록과 마이크의 유효 음성 입력 확인이다.** ‘투투스’ 맞춤 WakeNet, BNO085 방향·낙상, 양방향 통화는 완료 상태가 아니다. 모든 프로그램이 실제 안전모에서 검증됐다고 설명하면 안 된다.

다른 PC에서 GitHub 코드만 받으면 로컬 설정·DB·설치 환경은 따라오지 않는다. P4와 UWB 태그에는 기존 PC 서버 주소가 저장돼 있으므로 새 서버 PC 주소로 각각 설정을 맞춰야 한다.

## 2. 이어받을 저장소·브랜치·커밋

- 저장소: https://github.com/j91332992-dev/safe-halmat-capston-
- 브랜치: `feature/mobile-safety-app-20261001`
- 이 문서 작성 시작 시 코드 기준 커밋: `8d9fbc6`. 이 문서를 포함한 후속 문서 커밋도 받는다.
- 기존 PC 저장소: `C:\Users\조성준\OneDrive - pukyong.ac.kr\바탕 화면\hanmmir2.0`

| 커밋 | 주요 내용 |
|---|---|
| `ef7c68f` | P4 CSI 영상·C6 Wi-Fi 실물 구동 및 최신 데이터 기반 음성 응답 보완 |
| `d9b2846` | 부팅 시 스피커 TX 비활성, 실제 재생 때만 활성·종료 후 비활성 |
| `8d9fbc6` | 실제 UWB 프로젝트 경로 보완, 로컬 비밀설정 Git 제외, 태그 연결 복구 기록 |

새 PC의 영문 경로를 권장한다. 예:

```powershell
New-Item -ItemType Directory -Force C:\dev | Out-Null
Set-Location C:\dev
git clone --branch feature/mobile-safety-app-20261001 https://github.com/j91332992-dev/safe-halmat-capston- hanmir
Set-Location C:\dev\hanmir
git status
git log -5 --oneline
```

이미 작업 중인 저장소에서는 변경사항을 먼저 확인하고, 무조건 reset하거나 기존 작업을 덮어쓰지 않는다. 기존 ESP32-S3·UWB 프로젝트는 보존한다.

## 3. 현재 실제 확인 결과와 미완료 항목

| 항목 | 확인된 것 | 남은 것 |
|---|---|---|
| P4 보드 | DFR1172, ESP32-P4 rev 1.3, Flash 16MB, PSRAM 32MB, COM25 업로드·해시 검증 | USB 재연결·새 PC에서 COM 번호 재확인 |
| 내장 C6 | ESP-Hosted SDIO 4bit/40MHz, Wi-Fi·서버 heartbeat·WS 연결 | 장시간 동시 부하·AP/서버 재접속 시험 |
| 카메라 | OV5647 PID 확인, 800×640 캡처·JPEG·웹 원본 영상 | 사람/PPE 장면의 품질·정확도, 실제 FPS·지연 |
| YOLO | `backend/best.pt` 실제 로드·CPU 추론 | 안전모 영상의 PPE 인식률 평가·성능 조정 |
| 배터리 | MAX17048 SOC 약 9% 수신 | 실제 잔량 정확도·충방전 추적 |
| 스피커 | 명령 전달·WAV 완료 보고, 부팅 TX 비활성 수정 후 재업로드 | 실제 청취·음량·잡음 평가 |
| 마이크 | INMP441 I2S, WebRTC NS, AFE VAD 초기화 | 실제 발화 PCM·녹음 내용·STT·응답 전체 경로 |
| AI API | 기존 PC에서 인증 및 합성 음성 STT·설명 응답 확인 | 새 PC 키 설정, 실제 마이크 인식률·지연 측정 |
| UWB | 태그 Wi-Fi 전송 HTTP 200, 앵커 4개 온라인, 위치 이력 갱신 | 실제 앵커 좌표 등록·보정·실제 위치 정확도 |
| BNO085 | 핀 설정 후보 존재, 상태 `unverified` | 표준 UART/SHTP 드라이버·방향·낙상 구현/시험 |
| 호출어 | 서버 STT 결과에 별칭·유사도·후속 발화 게이트 적용 | ‘투투스’ 전용 로컬 WakeNet 모델 확보·평가 |
| 긴급어 | STT 결과의 긴급 표현은 호출어 없이 서버 판정 가능 | 로컬 긴급어 검출·오프라인 전달 보장 |
| 통화 | 기존 서버/웹 기능 존재 | P4 양방향 PCM 통화 미구현 |

초기 마이크 진단에서 PCM peak `1/32768`이 관측됐다. 이후 서버의 `last_audio_at` 갱신은 관측했지만, 이것만으로 실제 음성이 제대로 들어왔다거나 명령이 정상 인식됐다고 판단하지 않았다. **발화 중 PCM·서버 WAV·전사 내용을 함께 확인해야 한다.**

기존 서버 시험 77개 및 웹 TypeScript/Vite 빌드는 앞선 작업에서 통과했다. 이 인수인계 문서 작성 시 전체 시험을 새로 수행한 결과는 아니다.

## 4. 시스템 구조·주요 코드

```text
OV5647 → P4 CSI/ISP → 하드웨어 JPEG → 영상 전용 WebSocket
                                         ↓
                                   FastAPI → YOLO → React

INMP441 → P4 WebRTC NS → VAD/앞부분 보존 → WAV 업로드
                                                ↓
                      서버 STT → 호출어/긴급어 → intent/규칙/설명 AI
                                                ↓
                    Edge TTS → WAV → 별도 장치 명령 WS → P4 스피커

MAX17048 → P4 I2C1 → heartbeat → 서버/웹

UWB 앵커 4개 ↔ ESP32+DW3000 태그 → 자체 Wi-Fi → FastAPI 거리/위치 API
```

P4에는 내장 C6가 Wi-Fi를 담당한다. 외부 ESP32-C5는 초기 구조에 연결하지 않았고 ESP-NOW 통신도 사용하지 않는다. UWB 태그는 P4에 데이터선을 연결하지 않는다.

| 영역 | 주요 파일/폴더 |
|---|---|
| 현재 P4 통합 펌웨어 | `firmware/helmet_p4/` |
| P4 설정 | `sdkconfig.defaults`, `sdkconfig.dfr1172.example`, `main/Kconfig.projbuild` |
| P4 통신·명령 | `main/network.c`, `api_client.c`, `camera_transport.c`, `command_client.c` |
| P4 카메라·음성·센서 | `main/camera_source.c`, `voice.c`, `speaker.c`, `sensors.c`, `pin_guard.c` |
| 음성 실험 프로젝트 | `firmware/helmet_p4_voice_lab/` — 현재 안전모 통합 펌웨어와 구분 |
| 실제 UWB 다중 앵커 펌웨어 | `firmware/uwb_multi_test - 복사본/` |
| UWB 드라이버·도구 | `firmware/lib/Dw3000/`, `configure_wifi_tag.py`, `uwb_tool.py`, `uwb_live_bridge.py` |
| 서버 음성·Agent | `backend/app/routers/audio.py`, `services/audio_service.py`, `safety_agent_service.py`, `voice_execution_gate.py`, `tts_generator_service.py` |
| 서버 영상·위치 | `routers/camera.py`, `routers/uwb.py`, `services/camera_service.py`, `location_service.py`, `uwb_service.py` |
| 서버 설정 | `backend/app/config.py`, `backend/.env.example` |
| 웹 | `frontend/`, `frontend/vite.config.ts` |

`firmware/uwb_position_device` 등 다른 UWB 폴더에는 모의/미완성 드라이버 경로가 있으므로 실제 다중 앵커 태그에 잘못 업로드하지 않는다. 현재 사용한 것은 **`uwb_multi_test - 복사본`의 `tag` 환경**이다.

## 5. AI Agent 현재 모델·논리·한계

- STT: OpenAI `gpt-4o-mini-transcribe`, 한국어, 기본 제한 10초.
- 설명 생성: 설정상 OpenAI `gpt-6-luna`, reasoning none, 기본 최대 출력 80 tokens·제한 5초. 기존 PC의 단일 호출에서 확인한 설정이며 새 키에서도 접근 가능한지 확인한다.
- TTS: Edge TTS `ko-KR-SunHiNeural`, P4 재생용 16kHz/16bit/mono WAV.
- 배터리·PPE·위치·연결 상태 등은 서버 데이터·규칙으로 답하며 LLM을 호출하지 않는다.
- 긴급 표현은 일반 상태 질문보다 먼저 처리한다. 오래된 센서 값은 현재 상태로 단정하지 않고 ‘확인 불가’로 응답한다.
- 호출어 별칭 예: 투투스, 투투, 투투즈, 두두스. 서버 fuzzy 기본값 65는 매칭 임계값이며 인식 성공률 65%를 뜻하지 않는다.
- 현재 파이프라인은 **NS → VAD → 서버 STT → 호출어/긴급어 판단**이다. 맞춤 로컬 WakeNet이 이미 동작하는 구조가 아니다.
- 스피커 재생 중에는 마이크 구간을 버린다. AEC와 재생 중 긴급어 감지는 미완료다.
- 업로드 큐는 메모리 기반이다. 전원 차단·네트워크 실패 시 긴급 신고 보존·전달을 보장하지 않는다.

기존 PC 합성 음성 단일 연결 시험은 STT 약 7.0초, 설명 생성 약 3.7초, TTS 약 3.3초였다. 실제 마이크의 종단 지연이나 안정적인 성능 수치가 아니다. 사용자가 기억한 호출 성공률 60~70%도 정식 기준 시험 결과가 아니며, 현재 개선율을 숫자로 주장할 근거는 없다.

## 6. 새 PC 서버·웹 준비

기존 PC 실행 환경: Python **3.12.10**, Node **24.18.0**. Python 3.14에서는 선택 AI 패키지 일부가 설치되지 않으므로 재현에는 Python 3.12를 사용한다. ESP-IDF 전용 Python과 서버용 가상환경은 분리한다.

저장소 루트 PowerShell에서:

```powershell
py -3.12 -m venv backend\.venv
& .\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
& .\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-ai.txt
Copy-Item backend\.env.example backend\.env
Set-Location frontend
npm.cmd ci
```

위 `.env` 복사는 **새 파일이 없는 최초 설치 때만** 한다. 이미 설정된 파일을 덮어쓰지 않는다. `TEAM_SETUP_WINDOWS.bat`도 있지만 기본 서버 의존성 설치 중심이며 실제 YOLO에는 AI 의존성이 추가로 필요하다.

### backend/.env에 직접 설정할 항목

| 항목 | 설정 |
|---|---|
| `OPERATION_MODE` | `hardware` |
| `OPENAI_API_KEY` | 담당자가 발급·전달받은 유효 키를 로컬에 입력 |
| `CAMERA_INGEST_TOKEN` | 비어 있지 않은 토큰. P4 `HANMIR_CAMERA_TOKEN`과 동일 |
| `STT_MODEL`, `GPT_MODEL` | 현재 설정은 위 5절 참고. 새 계정의 접근 가능 여부 확인 |
| `YOLO_ENABLED`, `YOLO_MODEL_PATH` | `true`, backend 기준 `./best.pt` |
| `DATABASE_URL` | backend 기준 `sqlite:///./safety.db` 또는 새 PC 절대 경로 |
| `CORS_ORIGINS` | 사용하는 웹 origin. 아래 5173 예시에는 localhost/127.0.0.1:5173 |
| `SITE_WIDTH_M`, `SITE_HEIGHT_M` | 실제 현장 기준. DB의 기존 앵커/레이아웃 값도 함께 확인 |

기본 관리자 ID는 `TUTUS`이며 암호는 소유자에게 별도로 전달받는다. API 키·암호는 문서나 GitHub에 적지 않는다. `CALL_DEVICE_TOKEN` 등 기존 인증 설정도 사용하는 기능에 맞춰 별도 전달한다.

### 실행 — 창 2개

창 1, backend 디렉터리:

```powershell
Set-Location C:\dev\hanmir\backend
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

창 2, frontend 디렉터리:

```powershell
Set-Location C:\dev\hanmir\frontend
npm.cmd run dev -- --host 0.0.0.0 --port 5173
```

이번 PC와 같은 주소는 `http://localhost:5173`, 서버 문서는 `http://localhost:8000/docs`다. 저장소 Vite 기본 포트와 `TEAM_RUN_FRONTEND.bat`는 **5174**이므로 위처럼 5173을 지정하지 않으면 포트·CORS를 5174에 맞춘다. 새 PC에서는 가상환경 위치가 root `.venv`인지 backend `.venv`인지 구분한다. 위 절차는 backend `.venv`로 통일했다.

P4·UWB가 PC에 접속할 수 있도록 Windows 방화벽의 해당 서버 8000 포트 접근을 허용하고 같은 LAN을 사용한다. 방화벽 전체를 끄지 않는다. 휴대폰 웹을 쓸 때 localhost는 휴대폰 자신이므로 실제 서버 주소·웹 프록시·CORS를 확인한다.

## 7. PC 변경 시 반드시 맞출 네트워크 설정

| 이전 확인값 | 용도 |
|---|---|
| `192.168.0.40:8000` | 기존 PC FastAPI 서버 |
| `192.168.0.43` | 기존 P4 DHCP 주소 |
| `192.168.0.20` | 기존 UWB 태그 DHCP 주소 |
| `WISET_2.4G` | P4 내장 C6·UWB 태그가 연결한 AP |
| `COM25` / `COM6` | 기존 PC P4 / UWB 태그 USB 포트 |

이 값들은 자동으로 새 PC에 맞춰지지 않는다. P4 내장 C6는 2.4GHz AP를 사용한다. PC는 같은 공유기의 5GHz에 연결해도 LAN 상호 접근이 허용되면 된다.

1. `ipconfig`로 새 PC의 해당 LAN IPv4를 확인한다.
2. P4 `HANMIR_SERVER_HOST`와 UWB `HANMIR_SERVER_URL`을 새 PC 주소로 수정한다.
3. 카메라 토큰을 서버와 P4에서 일치시킨다.
4. 변경한 두 장치를 각각 재빌드·업로드한다. 서버 `.env`만 고쳐서는 장치에 저장된 목적지가 바뀌지 않는다.
5. DHCP 주소 변경 재발을 줄이려면 서버 PC의 공유기 DHCP 예약을 검토한다.

## 8. P4 펌웨어 재현·업로드

현재 확인한 ESP-IDF는 **5.5.5**다. Espressif 공식 설치 도구로 설치하고 해당 버전의 ESP-IDF PowerShell 환경에서 진행한다. 기존 PC의 `Initialize-Idf.ps1` 설치 식별자는 새 PC에서 그대로 사용하지 않는다.

기존 빌드 작업 경로는 `C:\dev\hanmir-p4\helmet_p4`였다. 새 PC는 영문 clone 경로의 `firmware/helmet_p4`에서 빌드해도 된다. **이전에 빌드된 같은 폴더의 sdkconfig가 있으면 먼저 별도 보관하고 설정 차이를 확인한다.**

최초 빌드:

```powershell
Set-Location C:\dev\hanmir\firmware\helmet_p4
idf.py -D "SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.dfr1172.example" set-target esp32p4
idf.py menuconfig
idf.py build
idf.py -p COM25 flash
idf.py -p COM25 monitor
```

COM25는 새 PC의 실제 P4 포트로 바꾼다. menuconfig의 **HANMIR P4 integration** 메뉴에서 SSID·암호·서버 IP/포트·카메라 토큰·ID를 설정한다. 연결하지 않은 부품은 해당 기능을 비활성화하거나 핀 `-1`로 유지한다. 예제는 기존 PC에서 연결한 부품 기준으로 카메라·음성을 활성화한다.

- 보드 rev 1.3: `CONFIG_ESP32P4_SELECTS_REV_LESS_V3=y` 및 16MB Flash/PSRAM 설정 확인.
- C6 SDIO: CLK18, CMD19, D0–D3=14–17, RESET54.
- 카메라: CSI 커넥터, SCCB SDA7/SCL8, OV5647 800×640 RAW8 모드, JPEG75·목표10FPS.
- INMP441: BCLK31, WS34, SD36, L/R=GND.
- MAX98357A: BCLK20, WS21, DIN22.
- MAX17048: **표준 I2C1**, SCL32/SDA33, 주소0x36. 카메라 SCCB도 주소0x36이지만 별도 버스를 사용한다.
- BNO085: UART RX23/TX51 후보. 현재 드라이버는 미구현이며 핀 설정만으로 동작하지 않는다.
- microSD GPIO39–45, 내장 C6 및 CSI 예약핀과 충돌하지 않도록 `pin_guard.c` 점검을 유지한다.

현재 펌웨어 버전 문자열은 `2.0.0-p4-hw-bringup-20261009`다. 같은 버전 문자열이어도 후속 수정이 있으므로 **Git 커밋도 함께 기록**한다. 부팅 시 스피커 송신은 켜지지 않아야 하고 실제 명령 때만 켜져야 한다.

`dependencies.lock`을 유지한다. 확인한 컴포넌트는 ESP-Hosted3.0.9, Wi-FiRemote1.6.5, ESP-SR2.5.5, ESP-Video2.5.0, ESP-Cam-Sensor2.6.0이다. C6 출고 버전이 0.0.0으로 표시돼 호스트 버전 경고가 있었으나 연결은 동작했다. 제조사 절차 확인 없이 내장 C6를 재플래시하지 않는다.

## 9. UWB 태그 재현·업로드 및 위치 문제

현재 실제 태그는 ESP32-D0WD-V3 + DW3000, USB CP210x(COM6)다. 앵커 번호는 펌웨어 0~3 ↔ 서버 anchor-001~004 대응이다.

저장소 루트에서:

```powershell
& .\backend\.venv\Scripts\python.exe -m pip install platformio
& .\backend\.venv\Scripts\python.exe configure_wifi_tag.py
& .\backend\.venv\Scripts\python.exe uwb_tool.py upload --role tag-multi --port COM6
```

설정 도구에서 2.4GHz SSID·암호·새 서버 PC IP를 입력한다. `wifi_secrets.h`는 Git 제외 파일이다. 도구는 프로젝트·라이브러리를 영문 경로에 복사하고 PlatformIO도 영문 코어 경로를 사용한다. 최초 설치에는 패키지 다운로드가 필요하다. COM6는 실제 태그 포트로 바꾼다. **앵커에 태그 펌웨어를 올리지 않는다.**

기존 PC의 수동 빌드 경로는 `C:\dev\hanmir-uwb-link\uwb_multi_test`였고, 글로벌 패키지의 한글 경로 컴파일 문제를 영문 경로로 해결했다. 이 경로와 패키지 junction은 새 PC에 필수 복사할 데이터가 아니다. 재현 도구의 영문 경로로 새 환경을 구성한다.

### 복구 결과

기존 태그의 목적지가 `192.168.0.27`로 남아 `POST failed: -1`이 반복됐다. `.40`으로 고친 태그 앱을 업로드하고 해시 검증했다. 18초 시리얼 관찰: 거리 프레임54개, 4앵커 수신53개, HTTP200 53건, 전송 실패0건. 원시 거리 중앙값은 3.50 / 2.04 / 1.04 / 3.89m였다. 태그와 앵커4개 모두 온라인이며 `last_uwb_at`과 위치 이력의 새 데이터로 수신을 확인했다. USB 브리지는 실행하지 않았다.

### 아직 해결하지 않은 위치 정확도

서버 등록 좌표는 `(0,0)`, `(5.8,0)`, `(5.8,8.2)`, `(0,8.2)`m이고 실제 설치 배치는 미확인이다. 신뢰도는 **0.05**였다. 이는 잔차 기반 코드 지표이며 정확도5%가 아니다. 관측된 거리 관계가 등록 좌표와 맞지 않아 계산된 위치를 실제 위치로 확정하면 안 된다.

담당자가 확인할 항목:

1. 1~4번 앵커의 실제 번호·좌표, 공간 가로·세로, 태그/앵커 높이.
2. DB에 등록된 앵커 및 레이아웃을 실제 배치로 수정. `.env`의 공간 크기만 바꾸고 기존 DB가 자동 갱신된다고 가정하지 않는다.
3. `uwb_calibration.json`과 서버 거리 보정 확인. 이미 보정한 거리를 다시 보정하지 않는다.
4. 현재 `location_service.py`는 수평2D 모델로 z값을 사용하지 않는다. 높이 차이 보정이 필요한지 실물 시험 후 결정한다.
5. 알려진 위치에서 정지·이동 시험. 필터가 작은 흔들림의 이력을 억제하므로 지도 점이 잠시 정지했다고 수신 실패로 판단하지 않는다. `last_uwb_at`도 확인한다.

USB를 빼도 태그 자체 Wi-Fi 전송은 가능하지만 안전모 전원은 유지돼야 한다. `uwb_live_bridge.py`는 USB 진단 대안이며 태그 직접 전송과 동시에 켜 중복 데이터를 보내지 않는다.

## 10. GitHub 외에 따로 인수할 로컬 데이터

| 데이터 | 전달/설정 방법 |
|---|---|
| API 키·Wi-Fi 암호·장치 토큰 | 소유자에게 별도로 전달받거나 새로 설정. MD/Git에 넣지 않음 |
| `backend/.env` | 새 PC 경로·토큰에 맞춰 재작성 |
| `backend/safety.db` | 기존 현장 좌표·이력·계정을 이어받으려면 별도 전달. 서버 중지 후 일관된 DB 사본 확보 |
| `backend/best.pt` | Git 추적 파일. clone 후 실파일 및 모델 로드 확인 |
| `uwb_calibration.json` | Git 추적 파일. 실제 설치의 보정값인지 확인 |
| P4 로컬 `sdkconfig` | 비밀값 포함. 필요하면 별도 전달 후 새 IP/포트/설정 재검토 |
| UWB `wifi_secrets.h` | 비밀값 포함. 새 PC에서 설정 도구로 재생성 권장 |
| 가상환경·node_modules·빌드 캐시 | 새 PC에서 재설치. 기존 폴더를 그대로 복사하지 않음 |
| 진단 로그·캡처 | 기존 PC `C:\dev\hanmir-runtime`에서 필요한 파일만 별도 전달 |
| P4 원본 전체 백업 | 기존 PC `C:\dev\hanmir-runtime\p4-original-flash.bin` 16MB. 비밀값 포함 가능하므로 Git 제외 |
| UWB 원본 진단 파일 | `uwb-tag-app-prefix.bin`은 앞부분256KiB뿐. 전체 복원용 백업이 아님 |

기존 DB를 전달하지 않으면 새 서버는 초기 데이터로 시작하며 기존 관제 이력·현장 배치가 자동 복원되지 않는다. 원본 백업·로그는 GitHub에 없다.

## 11. 다음 담당자의 실제 작업 순서

### 1순위 — 새 PC 연결 복구

1. 브랜치 clone, Python/Node/IDF 환경 구성, 비밀설정·필요 DB 인수.
2. 서버8000·웹5173 또는5174 실행. 모델 로드·관리자 로그인 확인.
3. 서버 LAN IP 확인 후 P4·UWB 목적지 및 토큰 갱신·업로드.
4. `GET /api/dashboard/snapshot`에서 hardware모드·장치 온라인·최근 수신 시각 확인.
5. 웹 원본 영상 및 서버 `GET /api/locations/worker-001/history?limit=5`의 새 UWB 이력 확인. 과거 DB 값을 정상 수신으로 오인하지 않음.

### 2순위 — UWB 정확도

실제 앵커 위치와 서버좌표를 일치시킨 뒤 알려진 위치에서 거리·필터·좌표를 비교한다. 정확도가 확인되기 전 대피 방향·위험구역 진입 위치를 정확하다고 보장하지 않는다.

### 3순위 — 마이크·음성 전체 경로

1. 배선·3.3V·L/R·I2S 채널 확인, 발화 중 PCM peak 및 WAV 내용 확인.
2. ‘투투스 배터리 얼마야’: 전사 → 호출어 → intent → 최신 배터리 답변 → 스피커 청취.
3. 시험임을 공유한 상태에서 ‘살려주세요’, ‘불이야’: 호출어 없이 긴급 판정·관제 기록·응답 확인. 시험 이벤트는 정리.
4. 화자·거리·소음·문구를 고정해 미탐·오탐·P50/P95 지연을 측정하고, 이후 맞춤 WakeNet/긴급어 모델·AEC를 검토.

### 4순위 — 영상·통신 성능

사람/PPE를 향한 장면에서 원본 품질부터 확인한다. 캡처 목표10FPS와 실제 수신·추론FPS는 다르다. 원본 수신FPS, YOLO처리FPS, 큐·드롭·종단 지연을 카메라 단독/음성 동시/UWB 동시로 측정한다. 기존 PC 추론은 CPU였으며 GPU 환경이라면 별도로 구성·기록한다.

### 그다음

BNO085 표준 UART/SHTP 실물 모드 확인과 드라이버 구현, 양방향 통화, 오프라인 긴급 보존, microSD 로그 등은 별도 구현·시험 후 완료 처리한다. GPIO는 사용자 최종 배선표와 보드 예약핀을 기준으로 관리한다.

## 12. 다음 담당자/Codex에게 그대로 전달할 요청

> HANMIR 2.0 작업을 이어받아 주세요. `feature/mobile-safety-app-20261001`의 최신 코드와 `docs/HANMIR_2_PC_HANDOFF_2026-10-09.md`를 먼저 읽으세요. P4 실물 기본 구동과 독립 UWB 태그 전송은 확인했지만 UWB 좌표 보정, 실제 마이크 인식률, BNO085, 맞춤 WakeNet, 양방향 통화는 미완료입니다. 새 PC 서버 주소·카메라 토큰을 P4와 UWB에 맞춰 연결부터 복구하고, UWB 실제 배치와 마이크 유효 입력을 우선 확인해 주세요. 기존 코드를 지우거나 GPIO를 임의로 확정하지 말고, 실제 로그와 최신 수신값을 근거로 작업하고 변경내용·남은 한계를 기록해 주세요.

이 요청과 MD는 작업 기준을 전달한다. 실제 HW·설정·유효 API 키가 없으면 자동으로 모든 기능이 완료되는 것은 아니다.

## 13. 함께 읽을 자료

- [2026-10-09 실물 구동·검증 상세 기록](HANMIR_2_P4_FIRST_BOOT_2026-10-09.md) — 초반 기록보다 뒤의 UWB복구 절이 최신.
- [P4 통합 펌웨어 안내](../firmware/helmet_p4/README.md)
- [P4 통신 개편 계획](HANMIR_2_P4_COMMUNICATION_PLAN_2026-10-02.md)
- [음성 준비 기록](HANMIR_2_VOICE_PREP_2026-10-02.md)
- [하드웨어 재설계 문서](HARDWARE_REDESIGN_ESP32P4.md), [현재 하드웨어 상태](CURRENT_HARDWARE_WIRING_STATUS.md)

문서 내용이 다르면 2026-10-01 사용자 최종 배선표와 실제 보드 확인, 최신 커밋의 코드·실물 로그를 대조한다. 오래된 설계 계획을 현재 완료 기능으로 취급하지 않는다.
