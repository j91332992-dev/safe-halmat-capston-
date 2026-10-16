# YOLO 상세 분석 분리·안전모 인식 개선 기록

작성일: 2026-10-16 (KST). 이전 보고서: YOLO_10FPS_TRIAL_2026-10-16.md.

## 요구와 유지 조건

- 전체 영상 YOLO 10FPS 목표. 보호구 검출을 희생하는 320 축소 방식은 채택하지 않는다.
- 기존 best.pt 가중치와 전체 640 입력, PPE별 판정 임계값 유지.
- 음성 처리 중 1FPS 우선순위 유지. 펌웨어·마이크·TTS 설정은 이번 작업에서 변경하지 않았다.
- 빠른 전체 영상 분석 FPS와 상세 보호구 분석 FPS는 별도 지표다.

## 구현

1. 빠른 분석과 상세 분석을 서로 다른 단일 프로세스 실행기로 분리했다.
2. 빠른 경로는 최신 프레임 큐 하나만 유지하며 전체 640 분석을 수행한다.
3. 상세 경로는 전체 640 + 사람 영역 640/960 분석을 유지하고 필요 시 머리 영역 640/960 검사를 추가한다. 동시에 실행되는 상세 작업은 전체 서버에서 최대 하나이며 대기 프레임을 누적하지 않는다.
4. 상세 분석용 파일을 별도로 복사해 빠른 경로의 임시파일 삭제와 충돌하지 않도록 했고, 완료 후 삭제한다.
5. 상세 결과는 제출 시각 기준 1.5초 이내, 현재와 이전에 모두 한 명의 사람이 확인되고 사람 상자 IoU가 0.5 이상인 경우만 결합한다. 이 조건은 공간 일치 확인이며 사람 신원 추적을 보장하지 않는다.
6. 상세 결과가 없거나 오래됐거나 사람이 바뀌면 PPE 값은 확인 불가(None). 빠른 프레임의 미검출을 상세 미착용 연속 횟수로 누적하지 않는다. 현재 프레임의 양성 검출은 바로 반영한다.
7. 이전 상세 프레임의 검출 상자를 현재 영상 좌표 위에 재사용하지 않는다. 상세 검출·원본 frame_id·age는 detail_evidence에 따로 포함한다.
8. 원래 코드에 있던 빨간 작업장갑의 hand+색상 근거 규칙은 유지했다. 장갑 신뢰도가 항상 순수 glove 클래스 확률을 뜻하지 않으므로 class/source/red_pixel_ratio를 함께 확인해야 한다.

## 안전모가 누락된 이유와 보완

원본에서 안전모 영역이 helmet보다 head로 강하게 분류된다. head를 helmet으로 재분류하거나 임계값을 낮추지 않았다.
상세 경로에서 확인된 한 사람의 상반신 안에 있는 head 후보(0.5 이상)를 머리 ROI 위치 제안으로만 사용한다.
가로 30%, 위 30%, 아래 40% 여유를 둔 원본 ROI를 640/960으로 검사한다. 별도의 helmet 클래스 검출이 기존 0.45 기준을 넘는 경우만 채택한다.

### 동일 원본 고정 비교

| 입력 | 기존 상세 방식 | 머리 검사 추가 |
|---|---:|---:|
| 안전모 착용 8장: helmet 검출 | 0/8 | 3/8 |
| 같은 8장: vest 검출 | 3/8 | 3/8 |
| 같은 8장: glove 검출 | 8/8 | 8/8 |
| 안전모 벗음 8장: 잘못된 helmet 검출 | 0/8 | 0/8 |
| 안전모 벗음 8장: vest / glove 검출 | 8/8 / 8/8 | 8/8 / 8/8 |

정답은 사용자가 착용/벗음 상태를 알려 준 원본이다. 양성 자료와 음성 자료의 첫 원본 화면도 시각 확인했다.
소량·같은 작업자의 인접 프레임이다. 일반화된 정확도/재현율이나 다른 색 안전모의 성능을 보장하지 않는다. 착용 8장 중 5장 미검출은 아직 남아 있다.

## CPU 병목 진단

원래 전체 640 + 사람 영역 640 + 960을 한 경로에서 기다려 처리했다.
분리 후에도 Ultralytics의 predictor 생성/재생성 시 torch 스레드 제한이 8로 되돌아오는 것을 실제 로그에서 확인했다.
pool initializer 또는 첫 setup 직후 제한만으로 충분하지 않았다. on_predict_start 콜백에서 매 호출의 제한을 확인하도록 변경했다.
실제 기록에서 fast=3, detail=1 유지 확인 후 상세 경로는 최종 설정에서 2개로 조정했다.
CPU 콜백 적용 구간(21:03:29~21:04:11 KST): 수신 10.67FPS, 전체 분석 6.83FPS, 상세 분석 0.83FPS. 음성 활성 상태 표본 1/19. GPU 전환 전 수치다.

## 실행 엔진 비교 및 선택

- ONNX CPU, OpenVINO CPU는 비교에서 더 느려 운영에 채택하지 않았다.
- 초기 CPU 비교는 라이브러리의 predictor 재생성으로 스레드 설정이 바뀔 수 있었던 실험이며 엔진의 보편적 성능 비교로 해석하지 않는다.
- Intel Core Ultra 5 125H의 Intel Arc iGPU가 OpenVINO에서 사용 가능했다. PyTorch CUDA 미지원과 내장 GPU 사용 불가는 같은 의미가 아니다.
- GPU FP32 고정 8장 비교: PyTorch 중앙값 109.59ms, OpenVINO GPU 25.02ms. 전체 640, 같은 가중치·후처리·임계값.
- 8장 모두 검출 텐서 shape 동일. 좌표/신뢰도/클래스를 포함한 원소 최대 절대 차이는 약 0.000305. 양자화하지 않았다. 모델의 모든 상황에 대한 일치 보장은 아니다.
- 빠른 경로만 선택적으로 GPU 사용, 상세 경로는 원래 PyTorch CPU 사용. GPU 초기화/실행 실패 시 기존 CPU 모델로 복귀하며 실패 프레임을 한 번 재처리한다.
- 첫 GPU 컴파일은 수십 초 이상 걸릴 수 있다. 모델 디렉터리 .cache 사용. 서버 수신 영상과 YOLO 분석 완료 시각을 구분해서 확인한다.

## 기록 항목과 파일

backend/logs/camera-analysis.jsonl에 lane, engine, frame_id, 실제 CPU threads, 분석 시간, 검출 클래스/상자/신뢰도, 모델 후보, PPE 판단, 상세 근거와 age를 기록한다.
모델 후보는 일반 모델 임계값 0.25 이상만 포함한다. 검출 신뢰도는 정확도가 아니며 검출 수는 서로 다른 사람 수가 아니다.
순환 로그는 현재 파일 20MiB + 백업 3개로 제한된다. 원본 사진은 시험 자료에만 로컬 저장하며 Git/외부로 업로드하지 않았다.

로컬 증거:
- C:/dev/hanmir-runtime/camera-split-fixture/raw-00.jpg 등 착용 원본 8장
- C:/dev/hanmir-runtime/camera-barehead-fixture/raw-00.jpg 등 벗음 원본 8장
- C:/dev/hanmir-runtime/split-fixture-comparison.json (최초 고정 비교)
- C:/dev/hanmir-runtime/camera-barehead-fixture-comparison.json
- C:/dev/hanmir-runtime/raw-helmet-probe.json
- C:/dev/hanmir-runtime/openvino-gpu-camera-comparison.json
- C:/dev/hanmir-runtime/split-camera-summary.json 및 yolo-split-*-measurement.jsonl

## 적용·재현·복구

- 필수 운영 경로는 기존 PyTorch. GPU 옵션 기본값은 false이며 이 PC의 backend/.env에서만 활성화한다.
- 선택 설치: backend/requirements-camera-experiments.txt. 실제 시험 버전 onnx 1.23.2, onnxruntime 1.31.0, openvino 2026.4.1, ultralytics 8.4.174.
- 모델 생성: YOLO('backend/best.pt').export(format='openvino', dynamic=True, quantize=32, imgsz=640).
- scripts/enable_camera_gpu.py로 이 PC의 GPU 빠른 경로 활성화. 원래 .env의 다른 설정은 출력하지 않는다.
- GPU 복귀: YOLO_FAST_OPENVINO_GPU=false 후 서버 재시작.
- 상세 분리 이전 방식: YOLO_ASYNC_DETAIL=false 후 서버 재시작. 전체/상세 해상도는 그대로 유지된다.
- 생성 모델 best.onnx, best_openvino_model/은 Git 제외. 원본 가중치로 재생성 가능하다.
- scripts/compare_split_fixture.py [원본 폴더], compare_openvino_camera.py GPU, report_split_camera.py로 증거를 재현/집계한다.

## 검사

- detail_merge 단위검사 5개 통과: 상세 없음, 신선한 동일 위치, 만료/위치 변경, 현재 양성 우선, 사람 신뢰도 미충족.
- Python 구문 검사 통과.
- 실제 추론 직후 thread=1 검증과 운영 fast=3/detail=1 로그 확인을 수행했다.
- 고정 이미지 양성/음성 비교와 실제 장치 연결 측정을 수행했다.
- Git 커밋/푸시는 아직 수행하지 않았다.

## 최종 운영 측정 — 21:10:20~21:11:02 KST

GPU 준비 완료 후 60초 수집 중 앞 15초를 제외한 42.03초 구간.
다른 모델 비교 프로세스를 동시에 실행하지 않았다. 음성 활성 표본은 1/19였으며, 자세와 발화 상태는 이전 구간과 완전히 동일하지 않다.

| 항목 | 값 |
|---|---:|
| 원본 수신 | 9.85 FPS |
| 전체 640 분석 완료 | 7.73 FPS |
| 상세 보호구 분석 완료 | 1.07 FPS |
| 전체 분석 시간 중앙값 / P95 / 최대 | 43.47 / 103.39 / 306.00 ms |
| 상세 분석 시간 중앙값 / P95 / 최대 | 740.86 / 1099.26 / 1170.78 ms |
| 분석 로그 개수 | fast 325 / detail 45 |
| 빠른 프레임에 결합 가능한 신선한 상세 결과 | 236/325 |

최종 실시간 로그에서 fast=openvino_gpu_fp32, torch threads=3 / detail=pytorch_cpu, threads=2를 확인했다.
이 구간 상세 검출 신뢰도(검출 항목 기준, 정확도 아님):

| 대상 | 검출 항목 수 | 최소 | 평균 | 최대 |
|---|---:|---:|---:|---:|
| 안전모 | 37 | .455 | .568 | .748 |
| 장갑 | 42 | .402 | .678 | .824 |
| 조끼 | 71 | .408 | .556 | .910 |

한 프레임에 전체와 상세 검출 항목이 함께 들어갈 수 있으므로 항목 수를 프레임 수나 사람 수로 해석하지 않는다.
이 라이브 구간은 사용자의 재착용 시점을 프레임별 라벨링하지 않았으므로 정답 기반 인식률 산출에 사용하지 않았다.

**10FPS 목표는 아직 미달이다.** 최초 동일 품질 순차 처리에서 2.13FPS였고, 현재 분리+GPU 구간은 7.73FPS지만 장면·음성 부하가 다른 실제 구간 비교다.
처리시간이 짧아져도 수신 간격, 100ms 속도 제한, 음성 우선 제한, DB/후처리 비용이 있어 완료 FPS는 추론시간 역수와 같지 않다.
다음 최적화는 수신 간격 및 단계별 후처리 시간 계측, 상세 분석 추가 가속, 음성 동시 부하 평가 순서로 진행한다.
모든 상세 검사를 초당 10회 실행한 것은 아니다. 미확인 결과를 착용으로 보간하거나 복제한 프레임을 FPS에 포함하지 않는다.
착용 샘플의 잔여 미검출, 다인원 구분, 물체를 손에 든 경우와 올바른 착용의 구분은 추가 검증이 필요하다.

추가 증거: C:/dev/hanmir-runtime/yolo-gpu-measurement.jsonl, yolo-gpu-live-out.log, yolo-gpu-live-err.log.
운영 오류 로그에서 이번 적용의 Traceback/실행 실패는 관측하지 않았다. 강제 GPU 고장 상황의 CPU 복구는 코드 경로만 마련했으며 실제 강제고장 시험은 하지 않았다.
스레드 설정 참고: https://onnxruntime.ai/docs/performance/tune-performance/threading.html
