# 카메라 밝기 및 안전모 추가 검증 — 2026-10-16

## 21:31 추가 적용 — 더 밝고 선명한 장갑 영상
- 현재 최종 설정은 감마 **1.35**, 약한 unsharp amount **0.2**, 미리보기 JPEG 재압축 품질 **95**. 아래 1.2 기록은 직전 비교 이력이다.
- 원본 해상도는 800×640 유지. 서버 보정으로 센서 세부 정보를 새로 복원하지 않는다. 저장된 P4 빌드 설정의 JPEG 품질은 75였으나 이번에는 P4를 재업로드하지 않았다.
- 동일 새 원본 24장 비교: 안전모 22→22, 조끼 22→23, 장갑 11→14 프레임. 장갑 검출 confidence min/mean/max는 0.464/0.655/0.780 → 0.432/0.603/0.756. 검출 프레임이 늘었어도 평균 confidence는 낮아졌으며 정확도 향상률로 해석하지 않는다.
- 기존 미착용 8장 안전모 오검출 0→0. 미착용 장갑 자료 검증은 아직 없다.
- 단위시험 9개 통과. 웹 재로그인 후 안전모/조끼/장갑 모두 착용 표시 및 새 영상 갱신을 확인했다.
- 45초 측정에서 워밍업 제외 28.238초: 수신14.77 FPS, 전체 추론7.61 FPS, 상세1.10 FPS. 음성 활성 상태 샘플2회. 장면/부하가 직전 측정과 달라 속도 변화가 보정 때문이라고 단정하지 않는다. 10 FPS 미달 유지.
- 증거: `camera-worn-validation2-bright135-comparison.json`, `camera-barehead-fixture-bright135-comparison.json`, `yolo-bright135-measurement.jsonl`, `brightness135-web.png` (모두 C:/dev/hanmir-runtime).
- 추가 파일: scripts/compare_bright135_fixture.py. gamma/sharpen 값은 상태 API 및 프레임별 분석 로그에 기록한다.

## 적용 상태
- 사용자 제공 사진을 밝기 참고로 삼아 서버 감마 1.2 적용. 센서 노출/게인 변경이나 P4 재업로드는 하지 않았다.
- 검은색/흰색 끝값을 유지하는 LUT로 중간 밝기를 올렸다. 촬영 조건이 다르므로 참고 사진과 동일한 밝기/화질을 보장하지 않는다.
- 웹 MJPEG와 앱용 corrected=true 이미지, YOLO 전체 및 ROI 입력에 동일한 보정 적용.
- `/live/image` 기본 응답과 저장 원본은 보정하지 않는다. 원본 검증 자료를 유지한다.
- 웹의 재연결 표시가 사라지고 영상/프레임 번호 갱신을 확인했다. 서버 재시작 시 웹 새로고침 후 연결을 확인했다.
- 밝기 설정: `CAMERA_DISPLAY_GAMMA=1.2`; 1.0으로 되돌리면 보정 없음. 변경 후 서버 재시작 필요.
- 안전모 추가 검사: `YOLO_HEAD_TIGHT_PROBE=true`. 기존 검사에서 안전모가 없을 때만 머리 주변 10% 여백 ROI를 480 크기로 추가 분석. 실제 helmet 클래스와 기존 0.45 기준 유지.

## 동일 원본 비교
| 자료 | 기존 상세 검사 | 좁은 ROI 추가 | ROI 추가+감마1.2 |
|---|---:|---:|---:|
| 기존 착용 8장: 안전모 검출 프레임 | 3/8 | 5/8 | 이번에 미측정 |
| 새 착용 24장: 안전모 검출 프레임 | 20/24 | 22/24 | 22/24 |
| 기존 미착용 8장: 안전모 오검출 | 0/8 | 0/8 | 0/8 |

새 영상에서 감마 적용 전후 조끼 검출 21→22장, 장갑 9→11장.
안전모 검출 confidence: 감마 전 min/mean/max=0.453/0.646/0.768, 감마 후=0.485/0.661/0.804.
Confidence는 정확도가 아니다. 한 사람의 인접 프레임이고 자세/시야가 다르며, 원본 수집에 동일 이미지가 포함될 수 있다. 24개를 독립 표본으로 해석하지 않는다. 장갑이 보이지 않는 장면도 있어 전체 검출 수를 recall로 해석하지 않는다.
기존 8장은 설정 탐색에 사용한 자료이고 새 24장은 그 이후 수집한 별도 시퀀스이다. 다인원/다른 조명/다른 안전모 검증은 남아 있다.

## 실시간 성능
최종 스레드 제한 후 측정: 21:25:53–21:26:36 KST 부근, 워밍업 첫 15초 제외한 42.995초.
- 수신 13.84 FPS
- 전체 화면 YOLO 6.21 FPS
- 별도 상세 분석 0.70 FPS
- 상태 샘플에서 음성 처리 활성 0회(샘플 사이의 짧은 호출까지 부정하지 않음)
- 10 FPS 목표는 미달. 화면 수신 FPS와 실제 추론 FPS를 구분해야 한다.
- OpenCV 기본 18스레드 확인 후 서버 및 분석 워커 각각 1스레드로 제한했다. 직전 보정 적용 측정 5.60 FPS와 촬영 장면/부하가 동일하지 않아 개선폭의 인과관계는 단정하지 않는다.
- 상세 분석 시간이 길어 TTL 1.5초 내 결과 사용률이 낮아질 수 있다. 오래된 판정을 재사용하기 위해 TTL을 무작정 늘리지 않았다.
- 다음 병목 분석은 전체 추론 지연의 긴 꼬리, CPU 상세 작업과 GPU 실행 경쟁, 상세 검사 단계별 비용을 분리해야 한다. 화질/임계값을 낮추어 FPS 수치만 올리지 않았다.

## 기록과 검증
- `backend/logs/camera-analysis.jsonl`: fast/detail/pipeline 구분, 후보 confidence, 좌표, 엔진, 감마, 추론 시간. pipeline은 대기시간과 후처리 시간 추가.
- `C:/dev/hanmir-runtime/camera-worn-validation2`: 새 원본 24장.
- `camera-worn-validation2-tight-comparison.json`, `camera-worn-validation2-gamma-comparison.json`: 프레임별 비교.
- `camera-barehead-fixture-tight-comparison.json`, `camera-barehead-fixture-gamma-comparison.json`: 미착용 검사.
- `helmet-roi-sweep.json`: 탐색 결과. 운영에서는 모든 후보를 실행하지 않는다.
- `yolo-bright-measurement.jsonl`, `yolo-bright-limited-measurement.jsonl`, `split-camera-summary.json`: 성능 자료.
- Python 구문 검사 성공. 상세 병합 및 밝기 단위시험 8개 통과. frontend production build 성공.
- 첫 pytest 실행은 저장소 루트의 import 경로 오류로 수집 실패했고 backend 디렉터리에서 재실행해 통과했다.

## 변경 파일
- backend/app/config.py: 감마, 좁은 ROI 옵션
- backend/app/services/camera_brightness.py: 공통 LUT와 미리보기 보정
- backend/app/services/camera_service.py: 원본/미리보기 캐시 분리
- backend/app/services/yolo_service.py: 전체/ROI 보정과 추가 안전모 검사, 감마 추적
- backend/app/routers/camera.py: 미리보기 응답, 보정 작업 스레드 분리, OpenCV 제한, 파이프라인 지연 로그
- backend/tests/test_camera_brightness.py: LUT 단위시험
- frontend/src/components/CameraMonitor.tsx, LiveCameraFrame.tsx: 보정 영상에 맞는 표기
- frontend/src/services/api.ts: 앱 미리보기 corrected=true
- scripts/capture_camera_fixture.py: 수집 수/간격 옵션
- scripts/compare_tight_helmet_fixture.py, compare_gamma_fixture.py, sweep_helmet_views.py, report_split_camera.py: 비교/측정

로컬 서버와 웹에 적용했다. 이번 단계에서 GitHub push, APK 재빌드, P4 재업로드는 하지 않았다.
