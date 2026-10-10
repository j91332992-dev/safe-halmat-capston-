# 지도 방향 실시간 갱신 — 2026-10-10

## 변경 이유

BNO085 SH-2 rotation vector는 기존에도 10Hz(100000us)로 읽었다. 하지만 서버에 보내는 방향값은 5초 heartbeat에만 포함돼 있고, 웹은 heartbeat마다 전체 snapshot/history를 다시 조회했다. 센서 입력 속도와 화면 갱신 속도가 달랐다.

## 반영 내용

- P4 command_client.c: 기존 /ws/device/{device_id} 명령 WebSocket을 공유하는 독립 heading task 추가. 최신 yaw/pitch/roll을 100ms 간격으로 보내며, 연결이 끊기면 송신하지 않는다. 송신 대기 시간은 30ms로 제한하며 과거 표본을 큐에 쌓지 않는다. 기존 5초 heartbeat는 유지한다.
- main.py: 장치 socket에서 orientation JSON을 수신한다. 크기 512자 제한, 등록된 assistant_device만 처리, 숫자/유한값/각도 범위 검증, 최대 20Hz 처리 제한. 현재 기존 장치 socket의 인증 정책을 따른다.
- orientation_service.py: 최신 방향만 프로세스 메모리에 보관한다. 샘플별 DB 쓰기를 하지 않는다. 2초가 지난 live 표본은 미확인 처리하며 과거 heartbeat 방향으로 되돌리지 않는다. 단일 서버 워커를 전제로 한다. 여러 워커에서는 공유 캐시/메시지 전달이 추가로 필요하다.
- serializers.py/devices.py: snapshot과 방향 보정 시 최신 live 값을 사용한다. 보정 offset은 기존 서버 설정을 유지한다. 센서의 yaw만으로 임의 북쪽 방향을 만들지 않는다.
- useSafetyData.ts: orientation 이벤트에서 해당 장치의 방향만 직접 갱신한다. 10Hz마다 전체 snapshot/history를 재조회하지 않는다. 진행 중인 느린 snapshot 응답이 더 최신 방향을 덮어쓰지 않게 수신 시각을 비교한다.
- SiteMap.tsx: 화살표 회전에 requestAnimationFrame과 80ms 보간을 사용한다. 359↔0도는 최단 회전 경로로 연결한다. 기존 지도 가로/세로와 Y축 반전을 반영한 각도 변환을 유지한다. live 방향은 3초 이상 오래되면 숨긴다. 기존 5초 heartbeat 장치에는 기존 15초 기준을 사용한다.

자동 지도 생성 기능은 다시 추가하지 않았다. 사용자 수동 X·Y 설정과 기존 앵커 배치를 유지한다. 실시간 방향은 휴대폰 자체 나침반이 아니라 안전모 BNO085의 방향이다.

## 빌드·업로드 및 실제 관측

웹 npm run build(TypeScript/Vite) 성공. ESP-IDF 5.5.5 P4 빌드 성공. 앱 바이너리 1890400바이트, 4MiB 앱 파티션 중 약 55% 여유. 데이터 USB COM25(303A:1001, 30:ED:A0:EA:5C:E2)를 확인하고 앱만 0x10000에 업로드, esptool 해시 검증 및 하드 리셋 완료. 파티션/음성 모델 데이터는 변경하지 않았다. 서버 재시작으로 새 수신 경로 반영.

실제 dashboard WebSocket을 12초 동안 관측: orientation 95건, 수신율 7.95Hz, 간격 중앙값 109.5ms, 최대 219.0ms. 동시에 location 38건, camera_frame 10건, heartbeat 2건을 수신했다. 이는 짧은 구간에서의 이벤트 수신 관측으로 전체 센서→휴대폰 지연, 카메라 FPS 또는 장시간 병목 부재를 입증하지 않는다. 정지 상태 yaw 범위는 -152.177~-152.085도였다.

사용자에게 안전모/BNO를 함께 좌우로 돌려 지도 화살표 반응과 방향을 확인하도록 요청했고, 사용자가 “ㅇㅇ 잘된다”라고 답했다. 특정 휴대폰/브라우저 종류와 정량 회전 지연은 별도 확인되지 않았다. 단위 테스트나 테스트 스위트는 추가·실행하지 않았다.

## 근거

- C:/dev/hanmir-runtime/p4-live-heading-build-20261010.log
- C:/dev/hanmir-runtime/p4-live-heading-upload-20261010.log
- C:/dev/hanmir-runtime/p4-live-heading-observation-20261010.json
- C:/dev/hanmir-runtime/backend-live-heading-v2-20261010.*.log

## 제한 및 인수 사항

새 서버 코드와 새 P4 펌웨어를 함께 사용한다. 이전 펌웨어는 기존 heartbeat 방향 갱신을 계속 사용한다. 서버를 다시 켜면 transient 방향 캐시는 비워지고 새 표본으로 복구된다. BNO 센서 읽기 함수의 기존 신선도 기준은 2초라 센서 자체가 멈췄을 때 이를 판별하는 시간은 별도로 발생한다. 실제 자기장 간섭·장착 방향·센서 보정에 따른 각도 정확도는 갱신 속도와 별개다. ESP-IDF 활성화는 한글 TEMP 경로 문제를 피하려고 TEMP/TMP=C:/dev/tmp로 실행했다. staging 경로는 C:/dev/hanmir-p4/helmet_p4이며 이번 변경 command_client.c를 원본과 동기화했다.
