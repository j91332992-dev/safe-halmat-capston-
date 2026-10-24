# HANMIR 영상·음성 전송 및 서버 병목 개선 기록 — 2026-10-24

## 1. 결론과 실제 사용자 확인

- 최종 무손실 WAV 전송을 켠 상태에서 사용자가 **호출·답변 속도 및 음질 정상**이라고 확인했다.
- 3분 양방향 자동 통화는 중간 재연결 없이 유지됐다. 이 구간에 UART 재부팅·패닉 기록은 없었다.
- **YOLO 10FPS 상시 유지 및 전체 음성 폐기 1% 미만은 아직 달성하지 못했다.** 서버 중계 폐기와 P4 내부 큐 폐기를 반드시 별도로 판단해야 한다.
- 이번 전원 조건은 P4 USB 연결이다. 이 비교에서 소비전력·사용시간을 계산하면 안 된다. 기존 배터리 단독 30분 시험의 약 3.75W·완충 약 5시간 추정은 과거 조건의 참고치이며 새 버전 절감량을 뜻하지 않는다.

## 2. 비교 조건

- 이전 비교: `power-optimization/before/20261024-163931`, 일반·TTS·통화 각 약 60초.
- 최종 비교: `power-optimization/after-stable/20261024-170329`, 17:03:30 시작. 일반 60초, TTS 60초, 양방향 통화 약 180초.
- 카메라 페이지가 열린 상태. 자동 통화는 PCM16 mono 16kHz, 20ms 패킷, 5초마다 1초 확인음과 나머지 무음이다. 사람의 실제 통화 명료도 시험과 다르다.
- 자동 TTS는 텍스트 주입이다. 호출어·마이크 STT 성공률을 자동 TTS 횟수로 계산하지 않는다. 사용자의 별도 실제 발화 성공 확인을 함께 기록한다.
- UWB 태그의 최신 수신이 중단돼 있었고 사용자는 앵커 3개만 켜져 있다고 알렸다. 이 비교로 UWB 동시 동작 정상 여부를 보증할 수 없다.
- 모델·임계값·추론 밝기/미리보기 밝기·해상도·JPEG 품질·UWB 필터를 변경하지 않았다. 사람/착용·미착용 정답이 포함된 인식률 재검증은 이번 비교에 포함되지 않는다.

## 3. 전후 측정

평균은 누적 카운터 차이/샘플 구간 시간이다. 마지막 구간 약 185초에는 통화 종료 처리 약 5초가 포함된다.

| 조건 | 수신 FPS 이전→이후 | YOLO FPS 이전→이후 | 상세 FPS 이전→이후 | JPEG 전송 B/s 이전→이후 |
|---|---:|---:|---:|---:|
| 일반 | 14.69→12.63 | 9.48→9.51 | 3.13→3.30 | 522,320→531,975 |
| TTS | 15.57→12.81 | 9.87→9.76 | 3.37→3.38 | 567,653→539,726 |
| 통화 | 14.82→13.06 | 9.39→9.61 | 3.20→3.42 | 587,837→550,451 |

- 통화 구간 JPEG는 약 6.4% 감소했지만 일반 구간은 증가했다. 장면·JPEG 크기가 달라 전체 조건의 확정 절감률로 일반화하면 안 된다.
- 최종 통화 5초 표본 YOLO: 4.79~11.20FPS, 37개 구간 중 20개가 10FPS 이상. 순간 10FPS를 넘은 것과 지속 10FPS 달성은 다르다.
- 촬영 목표 15FPS. 기존 정수 tick 간격으로 목표보다 많이 촬영하던 부분을 마이크로초 마감시간 기준으로 고쳤다. 전송 큐 여유가 없을 때 JPEG 압축을 건너뛰도록 했다.

## 4. 음성 전송량 및 통화 폐기

### 명령 WAV 무손실 전송

- 최종 시험 중 51개 파일: 원본 2,015,556B → 전송 1,546,896B, **23.25% 감소**. 멀티파트·TCP·Wi-Fi 헤더를 제외한 파일 본문 기준.
- 동일 WAV 바이트로 복원한 뒤 기존 STT에 전달한다. 음성 코덱/샘플률/인식 모델을 바꾼 것이 아니다.
- UART 압축 소요: 15.587~66.604ms. CPU 연산이 추가되므로 전송량 감소만으로 배터리 절감을 확정할 수 없다.
- 실제 발화 로그: 17:03:47 ‘투투스.’, STT 약 969ms. 17:03:52 ‘배터리 얼마요?’, STT 약 963ms. 이번 성공이 P4 로컬 웨이크워드 0.5초 달성을 입증하지는 않는다.

### 양방향 통화

- 연결 17:05:30.198 → 종료 17:08:30.073 부근, 약 179.9초. 연결 시도 1회, 시험 중 재연결 없음.
- 서버→P4 중계: 전송 5,733,120B, 대기시간 초과 폐기 21,120B, 약 **0.367%**. 용량 초과 폐기 0B.
- 서버→웹 중계: 전송 5,731,328B, 폐기 7,168B, 약 **0.125%**. 용량 초과 폐기 0B. 최종 상태에 writer error 1건이 있어 종료 시점 전후 원본 이벤트와 함께 해석해야 한다.
- **P4 내부 통화 수신 큐 폐기: 0→947,200B.** 서버→P4 전송량 대비 약 16.5%에 해당한다. UART 샘플과 서버 샘플 경계가 달라 정확한 패킷 손실률은 아니지만 무시할 수 없는 규모다. P4 송신 큐 폐기는 0B.
- 코드상 P4 RX 큐는 20ms×6=120ms. 서버 입력 최대 공백 약 828ms, 중계 최대 대기 375ms가 관측돼 재개 시 몰려오는 패킷을 120ms 큐가 흡수하지 못할 가능성이 있다. 원인 후보이며 네트워크/CPU/큐별 타임스탬프 대조 전 단정하지 않는다.
- 다음 개선은 서버 이벤트 루프 정체와 P4 도착·재생 간격을 함께 계측해 버스트 원인을 줄이는 것이다. 큐만 크게 늘리면 통화 지연을 늘릴 수 있다.

## 5. 메모리·플래시·안정성

- 설치 앱: 1,947,408B, 4MiB 앱 파티션의 약 46.43%, 여유 약 53.57%. 전체 플래시 점유율과는 다르다.
- 설치 앱 SHA-256: `B914ABB6BF59D466565F49490AAAC53752286D32C73CDECC5CB1559BC5DC164C`.
- UART 기록 중 최소 관측 내부 heap free 233,139B, 최소 관측 PSRAM free 30,227,688B. 누적 최소값은 heap 183,536B, PSRAM 30,141,292B. 메모리 누수 부재를 장시간 보증하는 수치는 아니다.
- 기록한 카메라 전송 표본 합: 3,960 시도 중 실패 2회, 표본 평균 전송시간 42~182ms. 누적 시도 카운터 전체와 혼동하지 않는다.
- 카메라 trace: 종료 시 enqueued/written 15,826/15,826, dropped/errors 0. UWB 로그 rotation_blocked/write_errors 0. 카메라 상태 DB 갱신 오류 0.
- 수집한 서버 프로세스 RSS 합 183,685,120~205,045,760B. 해당 수집기는 GPU worker RSS를 포함하지 않으므로 서버 전체 메모리라고 표기하면 안 된다.

## 6. 실제 변경 파일과 목적

- `backend/app/routers/camera.py`: WebSocket JPEG 메모리 전달, 일반 프레임 디스크 저장 생략, 실제 알림 증거 저장 유지, 카메라 상태 DB 갱신을 수신 ACK 경로 밖으로 이동.
- `backend/app/services/camera_service.py`: 미리보기 필요 시에만 생성·동일 프레임 공유.
- `backend/app/services/yolo_service.py`: 메모리 JPEG 디코딩 지원, 기존 파일 경로 호환 및 GPU fallback 유지.
- `backend/app/services/camera_trace.py`: bounded queue 512 + 별도 기록 스레드, 기록 폐기/오류 카운터.
- `backend/app/websocket/manager.py`: 화면별 bounded writer queue, 위치·방향·heartbeat 갱신 병합, 느린 클라이언트가 장치 수신을 막지 않게 분리.
- `backend/app/routers/devices.py`: heartbeat DB 작업 스레드 처리 및 무손실 업로드 지원 헤더.
- `backend/app/services/audio_service.py`: 제한된 zlib 복원·WAV 검증·전송/복원 바이트 계측.
- `backend/app/config.py`, `backend/.env.example`: `AUDIO_LOSSLESS_TRANSPORT_ENABLED`; 기본 false. 현재 PC 로컬 환경은 true.
- `firmware/helmet_p4/main/api_client.c`: 서버 지원 확인 후 이득 있는 파일만 무손실 압축. 미지원/압축 실패/압축률 부족 시 WAV 유지.
- `firmware/helmet_p4/main/voice.c`: 업로드 태스크 스택 6KiB→16KiB. 기존 VAD/마이크/호출 판정 설정 유지.
- `firmware/helmet_p4/main/camera_source.c`, `camera_transport.c`: 인코딩 전 큐 상태 확인 및 촬영 마감시간 계산.
- `firmware/helmet_p4/main/command_client.c`, `hanmir.h`, 서버 스키마: 재부팅 없는 촬영 목표 FPS 명령 지원. 현재 목표 15.
- `backend/app/services/uwb_log_service.py`, `scripts/shared_log_reader.py`: Windows 로그 회전과 관측 프로그램의 파일 잠금 충돌 완화. 위치 계산 변경 없음.

## 7. 발생한 회귀와 복구

- 최초 압축 시험에서 기존 6KiB `voice_upload` 스택이 부족해 Stack protection fault가 발생했다. 사용자가 지연·깨짐·무응답을 보고했다.
- 압축 기능을 꺼 기존 WAV로 복구하고 업로드 스택을 16KiB로 늘린 앱을 설치했다. 사용자 정상 확인 후 무손실 전송을 다시 켰으며 이번 최종 시험에서 패닉은 관측되지 않았다.
- 카메라 WebSocket 버퍼 64KiB 후보는 시험 도중 도입하지 않았다. **현재 설치 값은 16KiB**. SDK 전체 재빌드 후보가 중단된 이력이 있어 다음 빌드 전 올바른 환경으로 재구성해야 한다.
- 서버 설정으로 `AUDIO_LOSSLESS_TRANSPORT_ENABLED=false` 후 재시작하면 펌웨어는 다음 heartbeat 협상 후 기존 WAV 업로드로 돌아간다.
- 마지막 UART 기록에 호출과 무관해 보이는 ‘시키 그만 달라고’가 `life_critical_bypass`로 판정된 항목도 있었다. 기존 긴급 표현 매칭의 오탐 여부는 별도 정답 발화와 비교가 필요하다. 이번에 긴급 판정 임계값은 변경하지 않았다.

## 8. 재현·인수 및 남은 작업

1. 설치 앱 안전 사본: `C:/dev/hanmir-runtime/dual-wifi-20261024/power-optimization/p4-stable.bin`. 앱 오프셋 0x10000만 업로드했으며 NVS/모델/부트로더는 유지했다.
2. 이전 실제 장치 앱 파티션 백업: `firmware-before/device-app-partition.bin` (4MiB). 비밀번호·로컬 .env 백업은 Git에 올리지 않는다.
3. IDF 5.5.5 재구성 시 `ESP_IDF_VERSION=5.5`, `IDF_PATH`, `IDF_TOOLS_PATH`, `IDF_PYTHON_ENV_PATH`, `ESP_ROM_ELF_DIR`를 설정한다. `ESP_IDF_VERSION` 누락 시 esp_wifi_remote Kconfig가 잘못 구성될 수 있다.
4. P4 큐의 수신·재생·폐기 사유를 별도 계측해 통화 내부 손실을 줄이고, 그 후 3분 이상 재시험한다. 현재 보고서는 모든 병목 해결 완료 선언이 아니다.
5. UWB 태그/4개 앵커를 다시 켜고 최신 위치 데이터 포함 동시 시험을 해야 한다.
6. 소비전력 전후 비교는 USB·충전기를 모두 제거한 배터리 단독 조건을 사용해야 한다. 이전 보고서와 같은 부하/장면/배터리 상태로 충분한 길이의 시험이 필요하다.
7. 기존 미커밋 변경이 많다. 이번 작업과 이전 작업을 구분해 검토 후 커밋한다. 이번에는 GitHub push를 실행하지 않았다.

## 9. 원본 위치

기준 폴더: `C:/dev/hanmir-runtime/dual-wifi-20261024/power-optimization/`

- 이전: `before/20261024-163931/{samples.jsonl,events.jsonl,summary.json}`
- 최종: `after-stable/20261024-170329/{samples.jsonl,events.jsonl,summary.json}`
- 최종 UART: `uart-final-comparison.log`
- 실패한 최초 압축/재부팅 시험: `after/20261024-165004`, `uart-after-full.log` — 정상 전후 비교에서 제외.
- 자동 생성 원본 summary는 `summary.autogenerated.json`으로 보존. USB 조건에서 무효인 소비전력 계산은 검토 summary에서 null 처리했다.
