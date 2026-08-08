# 세 담당 통합 내역

## 기준 선택

위치/UWB 담당본이 지도 설계, 저장/적용 분리, 장애물, 위험구역 허용 작업자, 작업자 관리, 위치 기록, Wi-Fi UWB TAG까지 가장 최신이므로 기준본으로 사용했습니다. 음성본과 카메라본을 통째로 덮어쓰지 않고 실제 구현만 선별 병합했습니다.

## 위치/UWB·지도

- 4 앵커 거리 기반 2D 좌표와 Wi-Fi 서버 전송
- 5.8m × 8.2m 기본 작업장, 크기 변경 가능
- 앵커 드래그/좌표 입력, 장애물 이름·좌표·8방향 크기 변경
- 위험구역 이름·위치·크기·필수 PPE·허용 작업자 설정
- 설계 임시 저장, 버전 저장, 실제 적용 분리
- 작업자 이름·특이사항 관리와 위치 이력 재생

## 음성·AI

- 안전모 WAV 업로드와 OpenAI `gpt-4o-mini-transcribe` STT
- Responses API 기반 세이피 응답, 기본 모델 환경값 `gpt-5.6-sol`
- API 키/패키지/네트워크 오류 시 고정 안전 응답으로 자동 폴백
- Edge-TTS MP3 생성과 웹 재생
- 음성 명령을 비상 상태·위험도·이벤트·안전모 경고 WebSocket에 연결
- INMP441, MAX98357A, 버튼 실제 I2S 펌웨어 통합

## YOLO 카메라

- 팀원의 `best.pt` 한 개만 사용하고 중복 모델 제외
- ESP32-S3 OV5640 VGA JPEG 실제 multipart 업로드
- YOLO를 서버 이벤트에서만 표시하지 않고 작업자 PPE/화재 상태와 위험도에 실제 반영
- 안전모 미착용 위험도 +15점 추가
- 원본과 주석 이미지를 분리 저장하고 이벤트 사진 모달 제공
- 카메라 관제 전용 메뉴, 작업자 상세 미리보기, 모의 프레임 전송기 추가
- 카메라 HREF GPIO 7과 충돌하던 배터리 ADC를 GPIO 3으로 수정

## 보안·호환성 수정

- 팀원 펌웨어에 있던 Wi-Fi/비밀번호/고정 PC 주소를 최종본에 복사하지 않음
- `device_secrets.h`, `backend/.env`를 Git 제외 대상으로 지정
- 팀원별 절대 PlatformIO 빌드 경로 제거
- 한글 사용자 경로 대응 `av_tool.py` 추가
- Python 3.14에서 실패하던 SciPy/YOLO 문제를 Python 3.12 우선 설치로 해결
- NumPy 2.3.2/OpenCV 4.12 충돌을 NumPy 2.2.6으로 해결

## 완료 검증

- Python 자동 테스트: 16 passed
- 프론트엔드 TypeScript/Vite production build: 성공
- ESP32-S3 AV firmware: 성공, RAM 15.5%, Flash 29.7%
- 실제 `best.pt` 추론: 성공
- JPEG API→YOLO→PPE/화재→위험도→주석 URL 종단 테스트: 성공
- 테스트 이미지 결과: 4 detections, 위험도 70점(위험)