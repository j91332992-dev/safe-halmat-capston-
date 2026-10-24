# 양방향 통화 지지직 잡음 — 1차 수정과 계측

사용자 증상: 양방향 잡음·지지직. 2026-10-24.

## 변경 전 관측

통화 누적 서버 통계(동일 통화 전체의 정확한 시작·종료 시각은 별도 미확보):

- 안전모 입력 4,156패킷 / 2,128,384B.
- 관리자 입력 3,491패킷 / 2,234,240B.
- 서버→안전모: 대기 최대 359ms, 송신 최대 203ms, 입력 간격 최대 562ms, age 폐기 8,960B, 용량 초과 폐기 0.
- 서버→웹: 대기 최대 329ms, 송신 최대 235ms, 입력 간격 최대 1,375ms, age 폐기 6,144B, 용량 초과 폐기 0.
- 이는 끊김·클릭 가능성의 근거이며 모든 지지직이 이 원인이라고 확정하지 않는다. 실제 음향 녹음 및 당시 PCM 포화율은 없음.

## 확인한 코드 문제

- 웹 송신이 ScriptProcessor 2,048프레임을 사용. 48kHz 장치에서 약 42.7ms 간격으로 실행되어 20ms 네트워크 프레임이 묶여 전송될 수 있음.
- 프레임별 리샘플링에서 매번 위상을 초기화하고 길이를 반올림. 특히 44.1kHz에서 프레임 경계의 시각 일관성이 부족함.
- 수신 AudioBufferSource 재생이 250ms 이상 밀리면 다음 시작 시각을 앞으로 당김. 이미 예약된 소리를 취소하지 않아 서로 겹칠 수 있음.
- 브라우저 재생 부족·오버플로·PCM 포화·출력 샘플레이트를 서버에서 확인하는 계측이 없었음.
- P4 AFE의 AEC는 실제 스피커 재생 참조가 없어 비활성. 이번에 AEC가 구현됐다고 주장하지 않음.

## 1차 변경

- PCM16 mono 16kHz, 20ms/640B 통신 형식 유지.
- AudioWorklet 지원 환경에서 오디오 렌더링 스레드 사용.
- 마이크 리샘플링 위상을 청크 사이에 유지. 320샘플/20ms 프레임 단위 송신.
- 재생 프리버퍼 60ms, 최대 200ms 고정 링버퍼. 부족하면 재버퍼링하고 5ms 램프로 복귀, 부족 구간은 짧게 감쇠.
- 재생 시각을 되돌려 이미 예약된 음성과 겹치는 경로 제거.
- 마이크 경로 80Hz high-pass / 6.5kHz low-pass, 브라우저 수신 경로 80Hz high-pass / 6kHz low-pass. 잡음을 학습 제거하는 모델이 아닌 대역 제한 필터.
- 브라우저 echoCancellation/noiseSuppression/autoGainControl 요청은 기존 설정 유지. 실제 브라우저 적용 여부는 장치에 따라 다름.
- AudioWorklet 미지원 시 ScriptProcessor 512프레임과 연속 위상 리샘플링으로 호환 경로 유지. 이 경로에는 Worklet의 링버퍼 계측이 없음.
- 일반 ‘투투스’/STT, P4 펌웨어, 카메라 밝기·해상도·인식 임계값, UWB 좌표 설정은 변경하지 않음.

## 계측

5초마다 서버에 숫자 통계만 기록. 새 음성 파일 저장 기능은 추가하지 않음.

- txSamples / txClipped / txPeak / txRms.
- rxSamples / rxClipped / rxPeak.
- overflowSamples / underrunOutputSamples / rebufferCount / queueMs.
- outputRate / webDroppedSamples.
- `underrunOutputSamples`는 브라우저 출력 샘플 수 기준이며 초기 프리버퍼 대기도 포함. 16kHz PCM 손실 수와 혼동하지 말 것.
- overflowSamples는 브라우저 재생 링버퍼가 버린 16kHz 샘플, webDroppedSamples는 브라우저 송신 backpressure로 버린 16kHz 샘플.
- 서버 `/api/calls/{device_id}/status`의 `browser_audio`, `voice-pipeline.jsonl`의 `call_audio_metrics`.
- 서버는 검증된 숫자 키만 수용, 수신 빈도 최대 약 4초에 1회, 최근 장치 256개로 제한.
- `tools/call_quality_capture.py`: 원시 IMU 전송을 켜지 않고 통화·카메라·장치 수치를 2초 간격 기록.

## 적용·확인 범위

- 웹 TypeScript/Vite 빌드 통과. 서버 구문 확인·재시작 완료.
- 소스 및 웹 수정 적용. 기존 설치 APK는 자동 교체되지 않으므로 Android 네이티브 앱은 새 APK 빌드·설치가 별도로 필요.
- 실제 음질 개선은 사용자 청취와 활성 통화 계측 결과 확인 후 판정한다. 빌드 성공을 실제 잡음 해결로 기록하지 않는다.
- 이전 통화 원본 스냅샷: `C:/dev/hanmir-runtime/call-quality-before-20261024.json`.
- 수집: `C:/dev/hanmir-runtime/call-quality-20261024/`.

## 남은 점검

- 양방향 재시험에서 재생 공백·포화율·큐 폐기·카메라 FPS 비교.
- P4 내부 수신 큐/DMA 공백은 UART 로그 또는 추가 펌웨어 계측이 필요. 이번에는 P4 업로드를 하지 않음.
- 일정하게 나는 전기적 잡음·마이크 위치·스피커 피드백은 전송 버퍼만으로 해결됐다고 단정할 수 없음.

## 2차: 통화 네트워크를 화면 스레드에서 분리

1차 수정 후 사용자가 지지직이 남는다고 확인. 추가 계측에서 브라우저 송신 backpressure 폐기가 크게 발생해 다음을 적용했다.

- `hanmir-call-network.js` Dedicated Worker가 통화 WebSocket을 소유.
- MessageChannel로 AudioWorklet과 네트워크 Worker를 직접 연결. 마이크 PCM/수신 PCM이 카메라·대시보드의 메인 UI 스레드를 경유하지 않음.
- UI에는 상태·저빈도 음질 수치만 전달.
- 송신 backpressure 상한 6,400B(16kHz PCM16 200ms 분량). 무한 대기열을 만들지 않음.
- 사용자 확인: **안전모 마이크→웹은 잘 들림**, 웹→안전모는 조금 지지직이 남지만 개선됨.

## 3차: 안전모 스피커 방향 수정 및 업로드

- COM25 USB 로그 확인. I2S write_error=0인데 수신 큐 overflow가 지속됨.
- P4 call RX 준비 버퍼 약 60ms(20ms 프레임 3개), 수신 큐 6→12개(240ms 용량), 기존 200ms age 제한 유지.
- 수신이 끊기면 마지막 샘플을 짧게 감쇠해 무음으로 전환하고 재버퍼링. 재개 첫 32샘플(2ms)에 램프 적용.
- 통화 수신 음성만 75% 디지털 게인. 일반 TTS, ‘투투스’ 마이크 입력 및 인식 설정 변경 없음.
- heartbeat `component_status.call_diagnostics`에 RX/written/overflow/aged/write_error/silence/TX drop 카운터 추가.
- 버전 `2.0.0-p4-imu-shadow-cal2-call1-20261024`.
- 앱 크기 **1,965,232B**, 앱 파티션 잔여 **2,229,072B**.
- SHA-256 `64ba357d64894696f332c06b7df27e0a7529b985b6f8dff6f0906c6c42dea5dc`.
- 빌드 exit 0, COM25 앱 영역 0x10000 업로드 exit 0 및 Hash of data verified 확인. 재연결 후 펌웨어 버전·원격 call_diagnostics 수신 확인.
- 사용자 최종 확인: **“웹에서 하고 있음”, “통화 잘됨”**.

## 변경 단계별 실측

| 단계 | 브라우저 송신 backpressure 폐기 | 브라우저 수신 큐 폐기 | 활성 구간 YOLO | 상세 분석 |
|---|---:|---:|---:|---:|
| AudioWorklet 1차, 화면 스레드 전송 | 58.31% | 36.85% | 10.40FPS | 3.53FPS |
| 네트워크 Worker 분리 | 0% | 10.44% | 9.54FPS | 3.49FPS |
| Worker + P4 RX 수정 최종 | 0% | 11.52% | 8.59FPS | 3.29FPS |

- 각 비율은 해당 통계 창의 샘플 카운터 차이 기준. 모든 단계가 동일한 음성·영상 장면의 통제 실험은 아니며, 각 창 길이도 다름.
- 최종 활성 구간 표본 34개, 첫~마지막 77.11초. 영상 수신 10.28FPS, UWB 온라인 34/34.
- 최종 브라우저 송신·수신 PCM 포화 샘플 증가 0.
- 최종 P4 RX: 수신 2,157,440B, overflow 208,000B, aged 50,560B, write_error 0. overflow+aged/수신 약 **11.98%**. 이는 해당 기기 카운터 구간 기준이며 송신측에서 미리 버린 양까지 포함하는 종단 손실률은 아님.
- P4 silence_bytes 277,120B는 시작/재버퍼링에 넣은 무음도 포함. 모두 네트워크 손실이라고 계산하지 않음.
- 내부 힙 마지막 236,739B, 이번 부팅 이후 최소 165,924B, PSRAM 마지막 30,747,572B. 센서 스택 최소 여유 3,588B, IMU 전송 스택 7,676B.
- **청취 개선 확인은 통과. 수신 폐기 1% 미만 및 통화 중 YOLO 10FPS 항시 유지 목표는 미달.** 완전한 병목 해소로 기록하지 않는다.
- 최종 원격 통계 창 이후 UART에서도 수신 간격 최대 2,368ms가 관측됨. Wi-Fi/전송 지연과 긴급 재연결 문제는 추가 장시간 검토 필요.

## 재부팅과 낙상 기준

펌웨어 업로드로 P4가 재부팅되어 정상 자세 baseline_ready=false가 됐다. 서버에 이전 등록 정보가 남아 있어도 boot/generation 불일치로 실제 낙상 질문은 활성화되지 않는다. **낙상 기능을 다시 사용하기 전에 정상 착용 자세 확인 → 기준 저장 → 새 boot/generation으로 등록**해야 한다. 이를 자동 완료했다고 주장하지 않는다.

## 최종 자료

- 바이너리: `C:/dev/hanmir-runtime/hanmir-call-quality-20261024.bin`.
- 비교 JSON: `C:/dev/hanmir-runtime/call-quality-comparison-20261024.json`.
- 수집 3세션: `C:/dev/hanmir-runtime/call-quality-20261024/20261024-212434`, `20261024-212919`, `20261024-213330`.
- UART: `call-quality-uart-20261024.log`, `call-quality-final-uart-20261024.log`.
- 업로드/빌드: `call-quality-flash-20261024.log`, `call-rx-quality-build-final-20261024.log`, `call-worker-build-20261024.log`.
- 최신 웹/서버/P4 소스는 로컬 수정 상태. GitHub push 및 기존 APK 재설치는 이번에 수행하지 않았다.
