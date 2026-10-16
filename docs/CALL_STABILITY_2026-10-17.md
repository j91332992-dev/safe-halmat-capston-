# 웹 통화 끊김 수정 — 2026-10-17

## 변경 전
35초 UART 기록에서 통화 채널 재연결 3회. 마이크 입력 peak 최대7965/32768, 웹에서 받은 PCM peak 최대21615/32768, 스피커 I2S 쓰기 실패0회. 디지털 오디오 경로는 정상이나 연결 유지 불안정.

## 원인 및 수정
- 기존 TX 전송 제한20ms. 실패 시 클라이언트를 강제 stop/start했다.
- 설치된 esp_websocket_client 라이브러리는 실제 transport 실패 시 자체 abort/reconnect한다. 외부 stop/start가 중복되는 구조였다.
- TX 제한150ms로 변경. 실패 프레임 재전송 없이 대기큐를 비우며 라이브러리 자동복구를 사용한다.
- 큐6개 제한 유지. 지연·끊김 균형은 실측 필요.
- 5초마다 TX 성공/실패/최대 지연us, 연결·active 상태 기록. 통신 오류 이벤트 기록 추가.
- 웹은 장치 재연결을10초 대기하고 재연결 중 마이크 데이터 송신 중지.

## 적용
C:/dev/hanmir-p4/helmet_p4 및 저장소 call_client.c 반영. COM25 앱 영역0x10000에1942720바이트 업로드, flash hash 확인. 앱 파티션46% 사용(54% 여유). 카메라·음성 인식 설정 변경 없음.

## 자료
변경 전: C:/dev/hanmir-runtime/call-uart-live.log
변경 후: C:/dev/hanmir-runtime/call-uart-after.log

## 적용 후 실측
- 약80초간 양방향 통화 유지 후 시험 종료. 웹에서도 1분 이상 연결 상태 확인.
- 서버 누적: 안전모→웹 5000패킷/2560000바이트, 웹→안전모 3498패킷/2238720바이트.
- 수집한 통화 중 UART 구간: TX 실패0, 재연결0, 스피커 I2S 실패0. 두 UART 수집 사이 공백이 있어 전체 시간의 모든 프레임을 UART로 관찰한 것은 아님.
- TX 최대50.473ms 관측. 이전20ms 제한 초과가 실제 발생함을 확인.
- 부팅 직후 Wi-Fi 연결 전 Host unreachable 오류는 통화 시작 전이며, 통화 유지 실패 수치와 분리한다.
- 장시간/다른 Wi-Fi 조건 안정성 및 종단 음성 지연은 추가 검증 필요.
- 후속 로그: C:/dev/hanmir-runtime/call-uart-after-continued.log, call-after-end.json.
