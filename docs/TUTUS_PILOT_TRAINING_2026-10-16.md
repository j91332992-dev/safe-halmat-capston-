# 투투스 로컬 모델 학습 실제 진행 기록

## 상태

초기 모델 학습 및 int8 streaming TFLite 변환 완료. **운영 배포 불가, P4 로컬 호출 전환 미완료.**
기존 안전모 펌웨어의 서버 STT 호출 방식은 유지한다. 500ms 응답 성능은 아직 측정하지 않았다.
이 문서는 이전 모델 준비 문서의 '학습 미시작' 상태 이후 진행 기록이다.

## 사용자 정답과 데이터

- 1차 수집 69개를 사용자가 청취·분류: positive 9, negative 60, discard 0.
- 이 숫자는 발화 성공률이 아니다. 주변 소리, VAD 분할 등의 영향으로 파일 수와 발화 수는 다르다.
- 원본 WAV와 사람 라벨은 Git 제외된 `recordings/wake/20261016-pilot/`에 보존.
- 파일 SHA256 중복을 검사하고 원본 단위로 training 7/36, validation 1/12, testing 1/12 (양성/음성) 분리.
- 동일 화자·같은 녹음 세션이므로 화자 독립 평가가 아니다.
- VAD 후 클립이므로 연속 배경 오호출/시간, 발화 끝 지연 평가 자료가 아니다.

## 학습 재현

- upstream: https://github.com/OHF-Voice/micro-wake-word
- revision: `4665173cd35f1cff9a61e06fc427f124766c488e`
- 별도 환경: `C:/dev/hanmir-wake-training/venv` (운영 backend 환경과 분리).
- TensorFlow 2.21.0, keras 3.15.1, pymicro-features 2.0.2, ai-edge-litert 2.3.0.
- 전체 의존성: `C:/dev/hanmir-wake-training/pilot-v1/environment-freeze.txt`.
- prepare_wake_training.py → train_wake_pilot.ps1 → inspect_wake_model.py → evaluate_wake_pilot.py.
- 16kHz mono PCM16, microfrontend 40채널, 10ms step, clip 1500ms.
- MixedNet 5601 parameters (5473 trainable), CPU 2스레드, batch 16, 300 steps, learning rate .001.
- 양성 가중치 1 / 음성 가중치 5. best_weights export.
- 첫 실행은 TensorBoard 누락으로 중단; 설치 후 `model-run2`에서 완료. 실패 로그도 보존.
- 완료 로그: `C:/dev/hanmir-runtime/wake-pilot-train3.log`.

## 모델

- 파일: `firmware/wake_model_lab/main/tutus_pilot.tflite`
- 크기: 29,336 bytes.
- SHA256: `402f96e16879eabc35603fd7758f03ee44884b327d28f8903486d4b50985bdb8`.
- 입력 int8 [1,3,40], scale .10196078568696976 / zero -128.
- 출력 uint8 [1,1], scale .00390625 / zero 0.
- resource variables로 내부 streaming state 유지. 각 독립 클립 평가는 새 interpreter로 초기화.
- PC delegate 항목은 모델의 실제 연산으로 계산하지 않는다.
- 실제 연산: AssignVariable, CallOnce, Concatenation, Conv2D, DepthwiseConv2D,
  FullyConnected, Logistic, Quantize, ReadVariable, Reshape, SplitV, StridedSlice, VarHandle.

## 독립 실행 평가 결과

학습 도구의 출력만 믿지 않고 export된 양자화 모델을 전체 클립으로 다시 실행했다.
출력 tensor에 기록된 실제 scale을 사용했다. 기준 점수 **0.5**, 클립 내 최대 점수가 넘으면 검출:

| 구분 | 양성 검출 | 비호출 클립의 오검출 |
|---|---:|---:|
| training | 6 / 7 | 0 / 36 |
| validation | 1 / 1 | 0 / 12 |
| testing | 0 / 1 | 0 / 12 |

검증 데이터가 너무 작고 시험용 호출을 놓쳤으므로 배포하지 않는다.
threshold 0.7 이상은 validation 호출도 놓침. 시험세트를 보고 기준을 내려 성능을 주장하지 않는다.
이후 개발에 이미 확인한 시험 파일은 미사용 최종 시험으로 재사용하지 않는다.
상시 음원이 없어 false accepts/hour는 **미측정**. 도구의 nan 값은 0회/시간이 아니다.
평가 원본: `C:/dev/hanmir-wake-training/pilot-v1/clip-evaluation.json`.

## P4 준비

`firmware/wake_model_lab/`에 실제 모델 연산/메모리 실험 프로젝트 작성.
esp-tflite-micro 1.4.1 / ESP-IDF 5.5.5 / P4 revision 1.0 설정.
내부 resource variable 저장소를 할당하고 100회 Invoke 시간과 30ms 기한 초과를 로그로 남긴다.
128KiB는 예약 arena이며 사용량 실측값이 아니다.
마이크/카메라/통신이 없는 독립 실험 앱이므로 정상 안전모 펌웨어 대신 상시 설치하지 않는다.
빌드 및 실제 보드 실행 결과는 확인 후 별도로 기록한다. 현재 문서 작성 시 실물 실행하지 않았다.

## 추가 녹음

사용자 요청에 따라 2차 수집기를 실행했고 사용자가 투투스 30회 완료를 보고했다.
수집 종료 시 WAV **38개**, 총 **41.7초**, 전체 0값 클립 0개.
클립 RMS 범위 42.22~8084.44 (PCM16), 최대 포화 샘플 비율 약 0.0096%.
이 수치만으로 발음의 정확성/배선 정상 여부/인식률을 판정하지 않는다.
사람 분류 화면 http://127.0.0.1:8092, 데이터 `recordings/wake/20261016-session2/`.
수집 중간 집계33개 이후 종료까지5개 추가되어 최종38개다.
분류가 끝나기 전 자동 STT 결과를 정답으로 쓰지 않는다.
merge_wake_sessions.py는 완료된 사람 라벨과 세션 출처를 보존해 병합하며 기존 데이터는 변경하지 않는다.

## 다음 단계

1. 추가 사람 라벨 확보 및 원본 단위 학습/검증/신규 시험 분리.
2. 추가 데이터로 재학습. 소음/화자 독립 평가와 연속 배경 녹음은 별도 확보.
3. 동일 microfrontend를 P4에 통합하고 먼저 감지 점수만 기록하는 모드로 검증.
4. 검출 이벤트는 비차단 큐로 내장 ACK 재생에 전달. 안내 중 이중 감지 및 서버 중복 안내 방지.
5. 호출어 말미 → 실제 스피커 첫 소리의 최대 지연, 500ms 초과 수, 누락, 오호출을 함께 기록.
6. 카메라·UWB·음성 동시 부하에서 프레임 처리 기한, 메모리, 송신 대기 검증.
7. 비상어 로컬 경로가 없으면 기존 서버 감시를 유지. 로컬 투투스 하나만으로 모든 WAV 송신을 중단하지 않는다.

## 2차 학습 완료

사람 분류 최종 9 positive / 28 negative / 1 discard. 총 18 positive / 88 negative 병합.
원본 파일과 출처 세션을 provenance.json에 기록. 1차에서 보았던 시험 파일은 새 시험에 넣지 않았다.
새 세션에서 validation/test를 각 3 positive / 9 negative로 분리하고 나머지 12 positive / 70 negative로 학습했다.
같은 화자의 세션 내 분리이므로 독립 화자/새 환경 평가가 아님을 유지한다.
1000 steps, 음성 가중치 2, 나머지 MixedNet 구조 유지. best_weights 양자화 export 완료.

v2 SHA256: `42709ab464158d10ef48083269af60e06c1a9a433c946c46de9facb0d83c471d`, 29,336 bytes.
현재 lab 폴더의 모델은 v2이며 v1은 로컬 pilot-v1 폴더에 보존한다.

| 기준 점수 | validation 호출 검출 | validation 비호출 오검출 | test 호출 검출 | test 비호출 오검출 |
|---|---:|---:|---:|---:|
| 0.5 | 3/3 | 9/9 | 3/3 | 9/9 |
| 0.7 | 2/3 | 0/9 | 3/3 | 0/9 |
| 0.8 | 1/3 | 0/9 | 1/3 | 0/9 |

0.5로 설정하면 비호출도 모두 잡히므로 단순 threshold 하향은 해결책이 아니다.
0.7 시험 결과도 단 3개여서 높은 현장 인식률의 근거가 되지 않는다. validation 누락이 남아 운영 미승인.
위 표는 기준별 조사 결과이며 최종 threshold 확정/독립 제품 성능 검증이 아니다.
로그: C:/dev/hanmir-runtime/wake-v2-train.log, wake-v2-evaluation.log.
자료: C:/dev/hanmir-wake-training/pilot-v2/clip-evaluation.json, split_manifest.json, training_parameters.yaml.

P4 전처리는 pymicro-features 2.0.2와 같은 소스·설정으로 구현했다.
합성 PCM 8000 samples에서 PC 기준 48 frames, raw feature FNV checksum 3207448957.
실물에서 일치 여부를 로그로 확인한 뒤 모델 Invoke 검사를 진행하도록 했다.

## 초기 상태 오검출 원인 조사

v2 비호출 88개 중87개는 각 interpreter의 두 번째 출력에서 최대값을 기록했다.
첫 .5초에 무음을 삽입했으므로 이 피크는 실제 발화 이전 초기 상태에 해당한다.
대표 초기 점수 .53125 → .56640625 → .53125 → .48046875로 감소.
모델 시작·리셋 직후 감지 금지와 상태 안정화가 필요하다. 매 오디오 프레임마다 상태를 초기화하면 안 된다.
진단 목적으로 첫17개 출력(30ms씩, 출력 시퀀스 약510ms)을 제외하면:

- validation threshold .5: 호출3/3, 비호출오검출1/9.
- testing threshold .5: 호출3/3, 비호출오검출0/9.
- threshold .7 결과는 이전 표와 같음.

사후 분석 결과이며 이를 새 독립 성능 검증으로 간주하지 않는다. 실제 기기에서는 전원 기동 안정화 시간이 추가될 수 있다.
재현 옵션: evaluate_wake_pilot.py --ignore-startup-outputs 17. 기본값0은 초기 출력도 평가한다.
실제 threshold/연속 확정 횟수는 새 연속 음원과 실시간 점수 로그로 결정해야 한다.

## P4 실물 실행 완료

COM25 / ESP32-P4 revision1.0에 app 영역(0x10000)만 임시 업로드했다.
기존 bootloader, partition table, NVS, SR model 영역은 변경하지 않았다.
시험 후 보존된 정상 앱을 다시 업로드하고 hash verification 및 서버 재접속 확인 완료.

| 항목 | 실측 |
|---|---:|
| PC 대비 frontend 결과 | 48 frames, checksum 3207448957 일치 PASS |
| 500ms 합성 PCM 전처리 총 시간 | 14,281µs |
| 모델 arena 실제 사용 | 13,644 bytes |
| 실험 arena 예약 | 131,072 bytes |
| 내부 resource handles | 12 |
| Invoke 100회 평균 | 328µs |
| Invoke 최대 | 1,815µs |
| 30ms 기한 초과 | 0/100 |
| 시험 종료 internal free heap | 470,088 bytes |
| 실험 앱 전체 flash 크기 | 357,392 bytes |

합성 입력, 독립 앱, Wi-Fi/카메라 없음. 마이크 검출률·발화끝 지연·동시 부하 성능과 다르다.
13,644 bytes는 모델 arena 사용량으로 전체 전처리/큐/스택 메모리 합계가 아니다.
증거: C:/dev/hanmir-runtime/wake-board-v2/uart.log, result.json, flash-experiment.log, flash-restore.log.
실험 앱 hash: 1bbc0546115c19dcb2a891e051d3bc89c95c264724260c98363d51cae97bc729.
복구 앱 hash: e60580a9f017ea25456ce3f2ca3737ed90c7f98a941b82cd4a5e85fc918095a0.
복구 후 AV online/camera capturing/heading 갱신, UWB online을 서버에서 확인했다.

## 실제 마이크 감지 점수 연결

helmet_p4/main/local_wake.cc에 shadow-only 실행 경로 추가. 기본 비활성화.
AFE 출력에서 160sample 블록을 복사하고 독립 태스크가 같은 frontend 및 모델을 실행한다.
큐는12블록, 송신은 대기0이므로 모델이 지연돼도 마이크/VAD를 막지 않는다.
모델 arena 예약32KiB, 태스크스택8KiB. 모델 처리 실패 시 기존 서버 음성 경로 유지.
큐 누락 시 sequence 차이를 감지하여 상태 초기화 및 준비구간 재시작.
매초 peak/추론횟수/처리시간최대/큐대기최대/drop 수/후보 수 기록.
관측 후보기준 .70×1회, 초기1.5초 억제, 재생/통화구간 억제. 후보는 NO_ACTION으로 기록한다.
추가 분석에서 .70×3회 연속 규칙은 양성18개 모두 놓치는 것으로 확인하여 운영 규칙으로 채택하지 않았다.
1회 규칙은 점수 피크의 실제 시각을 관찰하기 위한 로그 전용이며 재생을 허용하는 확정 판정이 아니다.
20:32 KST에 통합 빌드와 COM25 앱 업로드를 완료했다. 실제 마이크 입력을 이용한 감지 점수 기록 모드가 실행 중이다. 후보 검출은 재생 동작을 일으키지 않으며, 기존 서버 STT 및 응답 경로를 유지한다.

## 20:33 작업 마감 및 카메라 작업 전 기준값

### 이후 정정: 20:35 기존 앱으로 복구

사용자가 호출 무응답을 보고하여 shadow 앱을 제거하고 기존 백업 앱으로 전체 앱 파티션을 복구했다.
복구 SHA256: e60580a9f017ea25456ce3f2ca3737ed90c7f98a941b82cd4a5e85fc918095a0. esptool 쓰기 해시 검증 성공.
아래 shadow 측정값은 복구 전 실험 기록이며 현재 실행 상태가 아니다.
20:34 수신 음성 3건에서 STT가 프롬프트 문장을 반환했고 stt_prompt_echo로 응답이 차단됐다.
복구 후에도 같은 STT 결과가 관측됐다. UART에 음성 큐 포화 및 약 2.6~3.0초 대기가 있어 복구만으로 해결됐다고 판정하지 않는다.
녹음 품질/STT 원인 구분과 사용자 재확인이 남아 있다. 추가 펌웨어 실험은 중단한다.

사용자의 5분 내 정리 요청에 따라 추가 학습·녹음 요청은 중단했다.
현재 단계는 로컬 모델 실행과 계측까지이며, 로컬 호출에 따른 0.5초 이내 응답 완료 상태가 아니다.

- 통합 앱 크기: 2,115,216 bytes, 앱 파티션 4 MiB의 약 50.4%.
- 업로드 검증: esptool 데이터 해시 일치, 재부팅 후 AV와 UWB 온라인.
- UART 25개 통계 구간: 추론 851회, 처리 최대 11.917ms, 큐 대기 최대 13.666ms.
- 큐 드롭 0, 기록된 deadline 초과 0, 모델 오류 로그 0.
- 내부 가용 힙 관측 최저 207,723 bytes, 부팅 이후 최저 157,448 bytes, 태스크 스택 여유 최저 4,208 bytes.
- 관측 구간 후보 로그 3개. 발화 정답과 대조하지 않았으므로 성공 호출이나 오탐으로 판정하지 않는다.
- 기존 음성 경로는 유지되지만 이번 짧은 계측에서 새 발화에 대한 스피커 응답을 별도 확인하지 않았다.

카메라 기준: 재부팅 직후를 제외한 약 16.95초 구간에 서버 수신 12.15fps, 분석 완료 3.60fps.
설정은 전송 목표 15fps, JPEG quality 75, 서버 분석 목표 4fps.
전체 30초 관측의 최근 추론 시간 필드는 88.2~317.0ms였으며, 모든 프레임의 시간 분포는 아니다.
UART 전송 표본은 20회 중 실패 0, 평균 전송 시간 75~131ms, JPEG 약 68KB였다.
최신 프레임 우선 처리에 따른 생략은 네트워크 패킷 손실과 구분한다.
짧은 구간이므로 장시간 무병목 또는 보호구 인식률을 확정하지 않는다.

다음 카메라 작업 순서: 동일 장면에서 수신 FPS와 분석 FPS 분리 측정 → 전송 대기와 추론 시간 확인 → 사람·헬멧·조끼 검출 결과 확인 → 병목에 맞춰 설정 한 항목씩 조정.

증거 파일:
- C:/dev/hanmir-runtime/wake-shadow-build4.log
- C:/dev/hanmir-runtime/wake-shadow-final-uart.jsonl
- C:/dev/hanmir-runtime/wake-shadow-final-summary.json
- C:/dev/hanmir-runtime/wake-shadow-camera-final.jsonl
- 이전 정상 앱 복구용: C:/dev/hanmir-runtime/wake-board-v2/known-good-app.bin

## 연속 상태 추가 진단

evaluate_wake_continuous.py로 시험용12개 클립을 순서를 고정해 이어 붙였다.
앞2초 및 클립 사이2초 합성 무음을 넣고 같은 interpreter/frontend 상태를 유지했다.
호출클립 종료 후1초까지 같은 구간으로 평가, .7×1회/2초 cooldown 적용.
호출 후보2/3, 비호출 후보0/9, 나머지 무음 후보0.
파일별 초기화 결과3/3과 다르므로 파일 단위 결과만으로 상시 인식 성능을 보고할 수 없다.
합성 무음은 현장 배경음 시험이 아니며, 이미 사용한 시험 자료의 사후 진단이다.
클립 끝은 정확한 발화 끝이 아니므로 이 자료로 500ms 응답을 계산하지 않는다.
자료: C:/dev/hanmir-wake-training/pilot-v2/continuous-probe.json.
