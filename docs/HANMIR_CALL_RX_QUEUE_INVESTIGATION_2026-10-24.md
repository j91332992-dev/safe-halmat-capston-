# HANMIR P4 통화 수신 큐 개선 — 2026-10-24

## 현재 상태: P4 업로드 복구 완료·서버/웹 재가동, 통화 성능 목표 미달

- 이전 업로드는 77%에서 끊겼다. PC 재부팅·USB 재연결 후 COM25로 앱 전체 1,949,152B를 재업로드했고 `Hash of data verified`, exit 0을 확인했다. 재시도 로그: `flash-recovery.log`.
- 서버가 새 버전 `2.0.0-p4-call-rx-20261024` 및 카메라 WebSocket 버퍼 65,536B를 실제 보고했다. 서버 8000·웹 5174 정상 접근, 카메라·방향·통화 채널 재연결 확인.
- 앱 파티션 전체 재기록으로 부분 업로드 상태를 해소했다. NVS·모델·부트로더는 지우지 않았다.
- 사용자는 직전 우선순위 조정 펌웨어에서 투투스 안내·배터리 답변 속도와 음질 정상이라고 확인했다. 최종 후보는 별도 재시험이 필요하다.

## 실제 시험 및 실패 결과

| 단계 | 통화 연결 횟수 | YOLO 평균 FPS | 상세 평균 FPS | P4 RX 큐 폐기 증가 | P4 RX 폐기율 |
|---|---:|---:|---:|---:|---:|
|server_only|1|8.94|3.29|1,192,320B|분모 직접계측 없음|
|priority|1|8.83|3.27|921,600B|16.08%|
|async_log|2|8.13|3.01|1,106,560B|20.13%|

- server_only: 메모리 영상의 불필요한 파일 삭제 호출 제거, 기존 펌웨어. 약 3분 통화.
- priority: P4 재생 태스크 우선순위 4→6, RX 도착/재생/대기/I2S 시간 계측 추가. RX 큐는 기존 6×20ms=120ms 유지. 최대 200ms 초과 대기 음성은 별도 aged 카운터로 폐기. 이번 기록에서는 aged=0이라 overflow를 숨긴 결과가 아니다.
- async_log: 위 펌웨어를 유지하면서 서버 음성 진단 로그를 비동기 bounded writer queue로 분리. 약 3분 안에 장치 채널 단절 1회, 자동 재연결 1회 발생. 단순 성공 시험으로 표기하지 않는다.
- 장면 변화로 JPEG가 약 42KB에서 약 66KB로 커졌다. 설정은 같아도 전송량이 달라 엄밀한 동일 장면 A/B 비교는 아니다.
- 실제 P4 수신 폐기율은 priority 16.08%, async_log 20.13%. 서버 중계 폐기율만 보고 전체 음성 폐기가 1% 미만이라고 하면 안 된다.

## 원인 근거와 수정

1. I2S 쓰기 최대 소요는 대체로 약 20~22ms인데 패킷 도착에는 수백 ms 공백과 버스트가 있다. 재생 하드웨어 쓰기 실패 카운터는 별도로 기록한다.
2. priority 단계에서 `call TX failed ... elapsed_us=1500633 connected=1`이 기록됐다. 송신 잠금/전송 대기와 큐 폐기 관계를 봐야 한다.
3. 설치 라이브러리의 `ESP_WS_CLIENT_SEPARATE_TX_LOCK` 설정이 꺼져 있었다. 라이브러리 소스에서 송수신이 `client->lock`을 공유하며, 해당 옵션은 이 경합을 줄이도록 제공되어 있다. 최종 후보에서 활성화했다.
4. 카메라 전송 버퍼를 16KiB→64KiB로 변경해 JPEG의 WebSocket 분할 횟수를 줄이는 후보를 준비했다. 밝기·색감·해상도·JPEG 품질·모델 임계값은 변경하지 않았다. 실제 FPS 개선 여부는 최종 업로드 완료 후 측정해야 한다.
5. 서버 watchdog에서 음성 업로드 DB commit 및 음성 로그 파일 append 중 이벤트 루프 정체가 관측됐다. commit과 녹음 파일 정리를 스레드로 옮겼고, voice trace는 queue 512/별도 writer로 분리했다. commit은 취소 시에도 완료를 기다려 Session을 닫는 경쟁을 피한다.
6. 서버 수정만으로 목표가 달성되지 않았다. 위 표의 실패 결과를 보존한다.

## 최종 후보 — 전체 업로드 및 실행 버전 확인 완료

- 버전: `2.0.0-p4-call-rx-20261024`
- 파일: `C:/dev/hanmir-runtime/dual-wifi-20261024/power-optimization/rx-queue/p4-separated-lock.bin`
- SHA-256: `8955c1d9f904b2a63d6a64b7a2289806ff6a085bb02c87b86b605d31535691d3`
- 앱 크기: 1,949,152B / 4MiB 앱 파티션, 약 54% 여유. 전체 16MiB 플래시 사용률과 다르다.
- `CONFIG_ESP_WS_CLIENT_SEPARATE_TX_LOCK=y`
- `CONFIG_ESP_WS_CLIENT_TX_LOCK_TIMEOUT_MS=2000` (라이브러리 기본값)
- `CONFIG_HANMIR_CAMERA_WS_BUFFER_BYTES=65536`
- 기존 sdkconfig의 Wi-Fi·GPIO 등을 지우면 안 된다. 기존 프로젝트는 sdkconfig.defaults만 바꿔서는 선택값이 덮어써지지 않으므로 실제 SDK 설정 두 항목을 확인해야 한다.

## 메모리 기록

| 단계 | 관측 최소 내부 heap free | 종료 시 누적 heap 최소 | 관측 최소 PSRAM free |
|---|---:|---:|---:|
|server_only|233,075B|180,360B|30,300,588B|
|priority|238,443B|180,228B|29,914,332B|
|async_log|232,055B|180,228B|29,954,060B|

- 최종 64KiB 후보는 `separate-lock/20261024-192218/` 및 `uart-separate-lock.jsonl`에 재시험 기록 중. 이전 실패 결과와 구분한다.
- USB 연결 중이고 사용자가 SW6106 충전도 연결했다. 이번 SOC 변화로 소비전력·배터리 사용시간을 추정하면 안 된다.
- UWB 태그는 오프라인이며 앞서 앵커 3개만 켜져 있다고 확인됐다. UWB 필터·30cm 기준은 수정하지 않았지만 이번 시험에서 최신 UWB 동시 검증은 하지 못했다.

## 변경 파일

- `firmware/helmet_p4/main/call_client.c`: 재생 우선순위 및 bounded 지연/폐기/I2S 계측.
- `firmware/helmet_p4/main/api_client.c`: 식별 가능한 펌웨어 버전. WAV 무손실 전송/업로드 16KiB 스택은 직전 정상 설정 유지.
- `firmware/helmet_p4/main/Kconfig.projbuild`, `sdkconfig.defaults`: WebSocket 잠금 분리·64KiB 버퍼.
- `backend/app/routers/audio.py`: 비동기 commit 대기·녹음 파일 정리, commit 소요 기록.
- `backend/app/services/voice_trace.py`: bounded 비동기 로그 writer와 폐기·오류 카운터.
- `backend/app/services/loop_watchdog.py`: 150ms 이상 정체 시 최대 1초당 1건의 스택 근거. 로컬 변수·소스 문자열은 기록하지 않는다.
- `backend/app/routers/camera.py`: 메모리 프레임 불필요한 파일 삭제 제외, trace 상태·event loop 종류 표시.

## 복구 및 시험 절차 (1~4 복구 완료, 추가 비교 중)

1. PC 재시작·USB 재연결 후 COM25 복구 확인 완료.
2. 최종 후보 앱을 0x10000부터 전체 재업로드하고 esptool의 해시 검증 성공을 확인한다.
3. 새 버전·64KiB 버퍼·마이크/카메라/방향의 재연결을 서버에서 확인한다.
4. `separate-lock/capture.py` 및 `separate-lock/run.py`로 UART/서버 메모리·FPS·통화 큐를 수집한다. 수집기는 60초 일반+180초 자동 양방향 통화다. 원본은 로컬 런타임에 있으며 서버 인증 정보가 포함된 수집 스크립트는 그대로 Git에 넣지 않는다.
5. 가능하면 보호구를 착용한 사람이 카메라에 보이는 조건으로 검사한다. 사용자가 준비 여부를 확인하기 전에는 착용 정답률 재검증을 완료했다고 쓰지 않는다.
6. 통화 종료 후 투투스→배터리 실제 발화로 마이크/TTS 복귀와 음질·속도를 확인한다.
7. 통화 RX 전체 폐기(overflow+aged)·송신 대기·재연결·5초별 YOLO FPS·heap/PSRAM을 비교해 목표 달성 여부를 판단한다. 아직 달성했다고 표시하면 안 된다.

## 원본

- 기준 폴더: `C:/dev/hanmir-runtime/dual-wifi-20261024/power-optimization/rx-queue/`
- 집계: `review.json`
- server_only: `20261024-171928/`, `uart-server-only.jsonl`
- priority: `priority/20261024-173705/`, `priority/uart-priority.jsonl`
- async_log: `async-log/20261024-174249/`, `async-log/uart-async-log.jsonl`
- 최종 후보 빌드/설정: `separate-lock/build.json`, `build-separated-lock.log`, `build-version-final.log`
- 업로드 중단 로그: `flash-separated-lock.log`
- 정상 복구용 이전 앱: `p4-call-rx.bin` 및 상위 `p4-stable.bin`. 현재는 최종 후보 앱 전체 재업로드·해시 검증·실행 버전 확인 완료.
- GitHub push는 이번 작업에서 실행하지 않았다.

## PC 재시작 이후 재시험 조건

- 자동 비교: 일반 60초 + 합성 양방향 통화 180초. 시작 19:22:19, 통화 시작 19:23:19.
- 현재 웹 원본 영상은 천장이다. 사용자는 보호구 준비 완료라고 답했으나 실제 영상에는 사람이 없어 상세 PPE 부하·정답률 검증으로 간주하지 않는다. 사람을 비추도록 추가 요청했다.
- 이번에는 UWB 태그의 최신 서버 수신이 복구됐다. 이전 시험의 UWB 오프라인 제한과 구분한다. 앵커 4개 최신 품질·위치 정확도를 검증했다는 뜻은 아니다.
- 종료된 서버가 남긴 고아 multiprocessing 자식 4개는 부모가 존재하지 않음·작업 폴더가 backend임을 확인해 정리했다. 현재 실행 서버/추론 자식은 유지했다.

## USB 복구 후 1차 결과 — separate-lock/20261024-192218

- 합성 통화 179.64초, 연결 1회·통화 종료 제어 이외 단절 기록 없음.
- 서버 샘플 집계 통화 구간 185초: 수신 7.64FPS, YOLO 5.95FPS, 상세 0FPS. 처음 60초는 수신 4.50FPS·YOLO 4.08FPS. 목표 미달.
- P4 실제 수신 5,674,880B, overflow 1,496,960B, aged 0B, I2S 오류 0B. 폐기율 26.38%. 수신 공백 최대 2,563ms, 대기 최대 120ms, I2S 쓰기 최대 22,058us.
- P4 통화 중 관측 최소 heap free 266,059B, largest block 163,840B, PSRAM free 30,647,216B. 부팅 이후 누적 heap 최소 214,172B·PSRAM 최소 29,864,968B.
- 서버 프로세스 및 추론 자식 포함 RSS 최대 2,011,627,520B. 실행 래퍼의 메모리만으로 서버 사용량을 대표하지 않았다.
- UWB 태그 온라인 49/50개 샘플. 온라인은 최신 수신을 뜻하며 앵커 거리 정답률 검증과 다르다.
- 웹 상세 화면 정지 원인으로 `BrokenProcessPool` 반복 예외 확인. 카메라 상세 프로세스가 사라진 최초 원인은 아직 확정하지 않았다. 새 코드에 5초 재시도 지연·깨진 pool 재생성·오래된 PPE 캐시 제거·실패/복구 횟수 상태 표시를 추가했다. 프로세스를 고의 종료시키는 재현 시험은 하지 않았다.
- loop watchdog에 Windows Proactor recv/accept 처리 중 150~수백 ms 정체가 반복 관측됐다. 이것만으로 OS 결함이라 단정하지 않는다. 같은 P4 펌웨어로 Selector loop 비교를 별도 실행한다.
- 비교용 임시 실행기 `selector-ppe/server.py`는 asyncio.Runner에서 SelectorEventLoop를 명시한다. 저장소 기본 시작 배치는 아직 변경하지 않았다. 현장 1대 시험용이며 향후 연결 규모·Windows 비동기 subprocess 요구사항은 별도 검토 대상이다.

## Selector 비교 결과 및 최종 복구

- 원본: `selector-ppe/20261024-192740/`, `selector-ppe/uart-selector-ppe.jsonl`.
- 약 3분 시험: 연결 시도 3회, 명시적인 device_offline 2회. 마지막에 추가 connected 알림도 기록돼 단절 없음으로 볼 수 없다.
- 서버 전체 통화 구간: 수신 9.08FPS, YOLO 7.46FPS, 상세 1.61FPS. 5초 YOLO 최저 0·최고 11.2FPS, 36구간 중 8구간만 10FPS 이상.
- RX 수신 증가 4,776,960B, overflow 867,840B, aged/I2S 오류 0B. 폐기율 18.17%. 패킷 공백 최대 968ms. 이전 후보보다 일부 수치는 개선됐지만 목표에는 미달했다.
- 카메라 JPEG 평균 585,551B/s = 약 4.68Mbps (서버에 수신된 JPEG만; Wi-Fi/TCP/WebSocket 헤더·재전송·반대 방향 제외).
- 통화 중 관측 최소 heap 265,875B, PSRAM 30,492,792B. RSS 집계기가 uvicorn 명령행만 찾아 임시 server.py 실행기의 메모리는 누락됐다. 이 구간 RSS=0이라는 자동 결과는 측정 불가로 정정했다.
- UWB 태그는 49/49개 서버 샘플에서 온라인. 앵커/거리 정답률 시험은 하지 않았다.
- **Selector 방식은 채택하지 않고 기존 uvicorn 기본 Proactor 서버로 되돌렸다.** 저장소의 기본 시작 방식도 변경하지 않았다.
- 현재 P4에는 해시 검증된 최종 후보가 실행 중이며, 서버에는 보호구 pool 복구/오류 카운터 보완이 적용돼 있다. 밝기·인식 임계값·투투스 판정·UWB 필터/30cm 기준은 변경하지 않았다.
- 최종 일반 상태 확인 기록: `restored-monitor.jsonl`. 실제 투투스/배터리 음질·응답은 사용자 재확인 요청 상태다.

## 남은 문제

1. 목표인 통화 RX 폐기 1% 미만·통화 중 YOLO 10FPS 지속·상세 3~5FPS를 아직 달성하지 못했다. 순간 11FPS/상세 2.9FPS 화면을 전체 결과로 대체하지 않는다.
2. 패킷 송수신 공백/버스트가 I2S 처리 시간보다 훨씬 크다. 서버 loop 지연·실제 Wi-Fi 전송/재전송·P4 전송 대기를 같은 시간축에서 더 분리해야 한다. 메모리 용량 부족이나 스피커 고장으로 단정할 근거는 없다.
3. 상세 프로세스 종료의 최초 원인은 미확정. 이번 코드는 복구 경로와 계측을 추가한 것이며 native crash/OOM의 근본 원인 해결을 입증한 것은 아니다.
4. 이번은 USB 연결 시험이므로 소비전력 절감률·완충 사용시간은 산출하지 않았다.

## 최종 일반 상태 복구 관측 (19:32~19:33)

- 기본 Proactor 서버로 복구 후 약 46.62초 관측: 원본 수신 10.60FPS, YOLO 8.24FPS, 상세 2.62FPS. 10FPS 지속 목표는 일반 상태에서도 아직 미달한다.
- 이 구간 상세 프로세스가 실제로 한 번 종료됐고, 추가한 복구 경로가 pool을 재생성했다. 이후 상세 완료 카운터·최근 박스 화면이 다시 갱신됐으며 마지막 detail_last_error는 null이었다. 따라서 자동 복구는 실제 장애에서 관측됐지만 프로세스 종료 원인 자체를 해결한 것은 아니다.
- 통화 채널 온라인, operator_connected=false: 자동 통화 시험은 종료돼 일반 호출을 시험할 수 있는 상태다.
- 서버 loop lag p95 185ms·최대 278ms. 이 값은 일반 상태 관측 중 마지막 200개 probe 기준이다.
- 웹 로그인·원본 영상·최근 보호구 박스·실시간 위치 표시 확인. 증빙: 로컬 `restored-camera.png`.
- 사용자에게 통화 종료 후 투투스→배터리 실제 응답 청취를 요청했고 아직 새 답변은 받지 않았다. 이전 ‘정상’ 답변을 이번 최종 설정의 검증으로 대체하지 않는다.

## 최종 사용자 음성 확인

- 2026-10-24, 최종 서버 복구 후 투투스 안내·배터리 답변의 청취/속도/음질 재확인 요청에 사용자가 “ㅇㅇ잘된다”라고 응답했다. 사용자 청취 기준 정상으로 기록한다. 정확한 호출 지연(ms)을 계측했다는 의미는 아니다.
- 앞 절의 “아직 새 답변은 받지 않았다”는 기록 이후 확인이 도착한 것이다. 현재 설정은 추가 변경하지 않는다.
- 통화 RX 폐기·YOLO 10FPS 지속·상세 분석 처리율 목표 미달 결과는 그대로 유효하다.
