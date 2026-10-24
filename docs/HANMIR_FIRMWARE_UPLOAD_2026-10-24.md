# 준비된 펌웨어 업로드 — 2026-10-24

## P4 완료
- USB COM25, Espressif 303A:1001, ESP32-P4 rev1.3, MAC 30:ed:a0:ea:5c:e2.
- ESP-IDF v5.5.5 앱 빌드 완료. 부트로더/파티션/음성 모델 영역은 유지하고 0x10000 앱만 업로드.
- 신규 변경: stop_evacuation 즉시 수신, 재생/다운로드 중 대피 음성 취소, 이전 세대 대기 대피 음성 폐기.
- 일반 TTS/통화에는 대피 취소를 적용하지 않음.
- 바이너리 1,945,184바이트, 4MiB 앱 영역 중 약 46.4% 사용.
- SHA256 e0c796f6b4ba1cd5dc6625469d09224cbcd8b5ce1cf917fa36b0c27d62d1b21b.
- esptool 4.12.0: write 및 Hash of data verified, 정상 reset 완료.
- 네트워크 AIHSLab2, 서버 192.168.0.222:8000 유지.

## 재연결 확인
- helmet-001-av online, network ready, camera capturing, video_transport connected.
- 배터리 약 84.17%, battery ready. BNO imu ready 및 방향값 갱신.
- mic initialized, speaker initialized. 실제 발화/청취 검증과 구분.
- noise_suppression은 장치 보고상 unavailable. 새로 정상화됐다고 주장하지 않음.
- 통화 채널 connected=1, active=0. 실제 양방향 통화 시험은 하지 않음.
- UART 관측: 내부 heap 약 260~271KB, 최저 204,092바이트, PSRAM 약 30.8~30.9MB, RSSI -38~-42dBm.
- 관측한 카메라 송신 묶음에서 실패 0, 평균 전송시간 123~281ms, JPEG 약 69.7KB. 센서 인코딩 최대 8~9ms.
- 짧은 후속 3.015초 구간: 수신 4.64FPS / YOLO 4.31FPS / 상세 2.32FPS, 서버 큐 0, 마지막 YOLO 51.3ms·상세 53.1ms.
- **이 구간은 10FPS 목표 미달이며, 업로드 성공과 성능 목표 달성은 다르다.** 이번에는 기존 영상 설정을 바꾸지 않았으며 다음 동시 부하 시험에서 원인을 분리해야 한다.
- 실제 화재 종료 버튼을 통한 재생 취소 청취는 미실시. 일반 장치 command API는 stop_evacuation을 허용하지 않아 단독 진단 요청이 HTTP 422였음. 실제 화재 취소 API는 직접 장치 WebSocket 명령을 보내는 별도 경로이므로 이 422를 펌웨어 수신 실패로 단정하지 않음.

## UWB 후속 업로드 완료
- 최초 포트 목록에는 P4 COM25와 Bluetooth COM4/5만 존재. UWB 태그 USB 포트 미검출.
- P4 완료 후 사용자 태그 연결 확인. COM6, CP210x 10C4:EA60, USB 일련번호 02E4F879로 기존 태그 확인.
- repo 및 ASCII 빌드 작업장의 최신 소스 동기화, 로컬 비공개 Wi-Fi 설정을 AIHSLab2 / 서버 .222로 갱신.
- tag-10hz-ws 빌드 성공. RAM 51,736/327,680바이트(15.8%), 앱 플래시 960,633/1,310,720바이트(73.3%).
- ESP32-D0WD-V3 rev3.1, MAC 48:9d:31:e9:6c:0c. 태그 업로드와 각 영역 Hash of data verified 확인. 정상 reset 완료.
- 태그 바이너리 파일 967,216바이트. 소프트웨어 빌드 표시의 앱 사용량 960,633바이트와 구분.
- 서버 online 및 최신 UWB 수신 복구, UART measurement interval 약 100,000us. 무선 측정 주기 및 서버 수신 기본 경로 확인.
- 이번에 올린 것은 태그이며 앵커 1~4번 펌웨어는 변경하지 않음.
- 정상 100ms 앵커 비콘/태그 슬롯 구성 유지. 새로운 자동 측량 기능은 포함되지 않음.

### UWB 재연결 후 남은 문제
- 실제 이동 시험은 미실시. 자동으로 들어온 거리/서버 로그만 관측.
- 약 9.9초·100회 서버 기록에서 computed 7 / position_rejected 3 / failed 90.
- failed 90회 중 기존 solver nonconverged 89회, 유효 앵커 부족 1회. 서버 422 응답을 Wi-Fi 패킷 유실과 혼동하지 않음.
- 이 구간의 유효 앵커는 대부분 1·2·4번 3개, 3번은 미수신. 전원과 기존 모서리 배치를 사용자에게 확인 요청.
- 좌표 계산 불가 사례: 지도 앵커 1=(0,0), 2=(5.6,0), 4=(0,3.7)m. 거리 1=3.241825m, 2=1.674335m, 4=3.614488m.
- 1·2 간 지도 거리 5.6m보다 태그→1+태그→2 합 4.916160m가 짧아 동일 평면의 정확한 거리 조건을 만족하지 않음. 2·4 쌍도 모순됨. 지도 치수·앵커 위치·거리 편향/가림 등을 확인해야 하며 소프트웨어/하드웨어 단일 원인으로 확정하지 않음.
- 단순히 반복 횟수나 허용 오차를 늘려 좌표를 강제 확정하지 않았음. 품질 가중과 점프 제한은 적용돼 있지만 위치 정확도/안정화 성공을 선언할 수 없음.
- UART 원문 출력은 큰 진단 JSON 때문에 usb_drop 증가가 있었음. 무선 측정/서버 전송과 별개이며 최종 delivery 카운터는 로컬 로그에서 확인.
- 최종 측정 505회 기준 beacon_acquired=57/beacon_lost=56도 확인. 반복 재동기화가 있어 통신 전체 안정화 완료로 표현하지 않음. 평균 측정 주기가 약 100ms라는 사실과 구분하여 후속 분석 필요.

## 서버에 이미 적용된 변경
- 호출어 없는 통화 종료: 통화 스트림의 별도 STT 작업, P4 신규 키워드 모델 아님.
- 관리자 전용 사람별 PPE 판정/중복 알림 억제.
- UWB weighted 신호 품질 가중 및 jump guard. 태그 펌웨어 변경 없이 서버에서 적용.
- 대피 경로 허용 폭·상대 방향 안내·안내 빈도 제한 및 화재 종료 시 새 안내 중단.
- 앵커 간 10초 측량은 설계 문서 단계이며 업로드 가능한 완성 기능 아님.

## 3번 앵커 연결 후 재확인
- 사용자 연결 확인 후 약 7.3초·67회 관측. 앵커 4개 사용 66회, 3개 사용 1회로 3번 수신 복구.
- 계산 성공 19회, 위치 보류 4회, 실패 44회(nonconverged 43, high_residual 1). 네 앵커 수신과 정상 좌표 확정을 구분.
- 중앙값: 1번 4.439m / 2번 1.522m / 3번 1.408m / 4번 3.642m.
- 특히 2번은 반사·가림 강한 의심 41/67, 의심 26/67. 3번은 정상 진단 65/66.
- 등록 지도 X 5.6m/Y 3.7m. 2→태그→3 거리 중앙값 합 약 2.930m가 앵커 2↔3 등록 거리 3.7m보다 짧음. 정확한 거리/배치 가정에서 모순이며 실제 간격 및 거리 편향 확인 필요.
- 각 앵커 거리는 비동시 중앙값이므로 위 합만으로 단일 주기의 위반율을 계산하지 않음. 개별 모순 사례는 앞 절 실제 단일 주기 기록 참조.
- 지도 치수는 자동 변경하지 않음. 사용자에게 실제 앵커 2↔3 간격/배치 확인 요청.
- 근거: C:/dev/hanmir-runtime/firmware-20261024/uwb-anchor3-connected-status.json.

## 로컬 근거
- C:/dev/hanmir-runtime/firmware-20261024/p4-manifest.json
- C:/dev/hanmir-runtime/firmware-20261024/hanmir_helmet_p4.bin
- C:/dev/hanmir-runtime/firmware-20261024/p4-postflash-uart.jsonl
- C:/dev/hanmir-runtime/firmware-20261024/p4-reconnect-status.json
- C:/dev/hanmir-runtime/firmware-20261024/uwb-manifest.json
- C:/dev/hanmir-runtime/firmware-20261024/uwb-tag-upload.log
- C:/dev/hanmir-runtime/firmware-20261024/uwb-postflash-uart.jsonl
- C:/dev/hanmir-runtime/firmware-20261024/uwb-postflash-server.json
- C:/dev/hanmir-runtime/firmware-20261024/uwb-nonconverged-case.json
- 비밀번호가 포함된 로컬 설정 백업은 Git에 추가하지 않는다.
