# 다른 PC에서 이어받기 — 2026-10-17 최종 상태

## 먼저 읽기

1. `../HANMIR_2.0_FULL_WORK_REPORT_2026-10-16_17.md`: 전체 작업·실측·남은 문제.
2. 이 문서: 새 PC 실행 및 누락 파일 안내.
3. `backend-performance.env.example`: 실제 사용 중인 비밀값 없는 성능 override.
4. `sdkconfig.validated.example`: 마지막 P4 빌드 설정의 비밀값 제거 사본. 실행 중 보드 설정은 변경하지 않았다.
5. `runtime-versions.json`: 현 PC Python 패키지 버전. 전체 재현 lockfile은 아니다.

브랜치: `integration/hanmir-final-prd-20261016`. 기존 설치 APK가 이 소스와 같다고 가정하지 않는다.

## 다운로드

```powershell
git clone --branch integration/hanmir-final-prd-20261016 https://github.com/j91332992-dev/safe-halmat-capston-.git hanmir
cd hanmir
```

기존 checkout에 수정이 있다면 덮어쓰지 말고 별도로 clone한다.

## 서버 환경

Python 3.12 기준이다. 아래 명령은 새 PC에서 실행할 절차이며 이번 업로드 과정에서 환경 설치를 다시 실행하지 않았다.

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt -r backend/requirements-optional-ai.txt -r backend/requirements-camera-experiments.txt
```

`backend/.env.example`을 새 `backend/.env`의 기준으로 쓰고 이 폴더의 `backend-performance.env.example` 값을 병합한다. 기존 `.env`를 통째로 덮어쓰지 않는다. OPENAI_API_KEY, 장치 인증 토큰, 관리자/현장 DB 등은 기존 담당자에게 별도로 전달받는다.

실제 DB·지도·비상구·방향 보정·장치 등록 정보는 이 Git 커밋에 포함하지 않는다. 기존 환경을 그대로 이어받으려면 운영 DB를 일관된 SQLite backup으로 이관해야 한다. 빈 DB로 실행하면 기존 현장 구성이 자동 복원되지 않는다. 이관 파일에는 개인정보/인증 정보가 포함될 수 있으므로 공개 저장소에 올리지 않는다.

## GPU 모델

원본 `backend/best.pt`는 기존 저장소 추적 파일이다. 변환된 로컬 OpenVINO 출력은 Git에 포함하지 않는다. Intel Arc/OpenVINO 지원과 드라이버가 필요하며 다른 GPU/CPU의 속도는 별도 측정한다.

640 FP32 변환(저장소 루트에서):

```powershell
.venv/Scripts/python.exe -c "from ultralytics import YOLO; YOLO('backend/best.pt').export(format='openvino', imgsz=640, half=False, dynamic=False)"
.venv/Scripts/python.exe scripts/export_detail_gpu960.py --output backend/models/detail_gpu960
```

두 번째 명령은 대상 디렉터리가 이미 있으면 거부한다. 출력된 모델 경로를 확인한다. 서버를 backend 디렉터리에서 실행하므로 예시 `YOLO_DETAIL_GPU960_MODEL_PATH=./models/detail_gpu960/best_openvino_model`이 맞는지 확인한다. 640은 `backend/best_openvino_model`을 사용한다.

## 실행

```powershell
cd backend
../.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

별도 터미널에서:

```powershell
cd frontend
npm ci
npm run dev -- --host 0.0.0.0 --port 5174
```

현재 PC 주소192.168.0.40은 새 PC에서도 같다고 가정하지 않는다. P4/태그/모바일 서버 주소와 Wi-Fi, 방화벽, CORS 설정을 실제 환경에 맞춘다. 기존 장치를 같은 서버주소로 쓰려면 예약IP 등 네트워크 조건이 필요하다. 비밀번호는 공개 MD로 전달하지 않는다.

## P4 — 정상 설정 보존

이미 정상 펌웨어가 올라간 보드는 인수인계만을 이유로 다시 flash할 필요가 없다. 다시 빌드할 때 ESP-IDF5.5.5 환경에서 firmware/helmet_p4를 사용한다. Windows 한글/공백 경로 문제를 피하려면 전체 저장소 또는 필요한 형제 폴더 구조를 ASCII 경로에 둔다. `../wake_model_lab/components` 의존성이 있어 helmet_p4만 단독 복사하면 부족하다.

새 빌드 디렉터리에서만 `sdkconfig.validated.example`을 helmet_p4/sdkconfig로 복사하고 비어 있는 Wi-Fi SSID/password, 서버 URL, 카메라/통화 토큰을 menuconfig로 설정한다. 현재 로컬 sdkconfig를 덮어쓰는 자동 스크립트는 제공하지 않았다. 비밀값 제거 사본은 그대로 flash할 수 있는 완성 설정이 아니다.

```powershell
cd firmware/helmet_p4
idf.py menuconfig
idf.py build
idf.py -p COM포트 flash monitor
```

- LOCAL_WAKE_SHADOW/WAKENET/외부NS는 OFF 유지. pilot 모델은 후보 기록 시험용이며 운영 호출 모델 아님.
- 현재 통화 TX8KB, 절전해제, 카메라 복구 및 TTS 버퍼 변경은 소스에 포함.
- 실제 마이크 GPIO31/34/36, 출력20/21/22 등은 설정본과 기존 배선 문서를 대조.
- 이전 stage 폴더의 빌드 파일에는 미적용 실험본이 있을 수 있어 그대로 쓰지 않는다.

## UWB

`firmware/uwb_multi_test`를 기준으로 사용한다. wifi_secrets.h는 별도 전달/작성한다. 태그는 `tag-10hz-ws`, 1번 앵커는 `anchor-01-10hz`. 둘의 프레임 주기가 일치해야 한다. 2~4번은 기존 응답 펌웨어를 유지하며 이번 변경만으로 재업로드할 필요는 없다. 자동 지도 측량은 사용하지 않는다. 지도 XY와 앵커 위치는 실제 현장에 맞춰 수동 설정한다.

## 마지막 음성 정상 상태

STT gpt-4o-mini-transcribe/ko와 기존 prompt 전달을 유지한다. `whisper_service.py`의 prompt를 제거하면 짧은 투투스 인식이 다시 악화될 수 있다. prompt echo 차단도 유지한다.
최종 실제 호출3건+배터리1건 및 사용자 정상 청취 확인. 현재 P4 로컬 웨이크워드 직접 실행은 OFF이며 서버 STT 기반이다. 통화 중 AI 호출은 중지된다.

## 실기 확인 순서

1. P4/태그 heartbeat와 최신 수신 시각.
2. 확인음과 투투스→배터리 질문, 실제 청취.
3. 영상 수신/전체YOLO/상세PPE를 별도 FPS로 확인.
4. UWB 정지/보행·방향 보정.
5. 웹 양방향 통화, 마이크 양쪽 및 종료 후 AI 복귀.
6. 장시간 FPS/큐폐기/heap/재부팅 확인.

최종 약3분 통화 평균YOLO11.087FPS였으나 최저5초창8.595, P4 RX큐 약2.8%폐기, 맨손 장갑오탐이 남아 있다. 이를 해결 완료로 보고하지 않는다.

## Git에 없는 자료

개인 녹음/현장 원본사진, runtime JSONL 전체, DB, 인증정보, 전체Flash백업, 변환GPU모델, 기존 PC의 C:/dev 절대경로 파일은 별도다. 상세MD 수치와 파일 경로는 보존했다. 원본까지 필요하면 담당자에게 선택적으로 전달받는다. 앱은 최신 소스로 다시 패키징하고 Android/iOS에서 따로 검증해야 한다.
