# 지도 시선 방향 표시

## 구현

- BNO085 yaw에 현장 보정값을 적용하여 지도 방향을 표시한다.
- 현재 앵커 1 (0,0), 앵커 4 (0,8.2)의 벽을 정면으로 바라보면 지도 왼쪽이다. 해당 벽에 수직인 방향으로 보정한다. 특정 앵커의 점을 바라보는 보정은 아니다.
- 사용자 ‘벽 보고 있음’ 확인 후 웹의 보정 버튼으로 기준 저장 완료. 최초 지도 표시: 왼쪽 180도.
- 지도 작업자 아이콘에 파란 화살표와 시선 부채꼴 표시. 위치 이동 경로와 독립적으로 센서 회전에 따라 갱신한다.
- 지도 X/Y 화면 축척 차이를 반영하여 화살표 각도를 계산한다.
- 지도 각도: 오른쪽 0도, 위쪽 90도, 왼쪽 180도, 아래쪽 270도. 지리적 동서남북은 아니다.
- 센서 데이터가 15초 이상 오래됐거나 장치가 오프라인이면 ‘확인 불가’, 화살표 숨김.
- 보정값은 Device의 component_status_json에 저장한다. 펌웨어 heartbeat가 해당 서버 보정값을 덮어쓰지 않게 보존한다. 다른 PC도 같은 서버에 연결하면 동일 기준 사용.

## 사용

센서와 안전모/카메라의 상대 방향을 고정하고, 앵커 1·4 벽을 정면으로 본 상태에서 지도 ‘앵커 1·4 벽을 정면으로 보고 보정’ 버튼을 누른다. 센서 장착 위치 또는 현장 앵커 배치가 바뀌면 다시 보정한다. 현재 방식은 센서 yaw의 회전 변화에 오프셋을 적용하므로 센서의 올바른 장착 축이 필요하다. 눈동자 시선 추적 기능이 아니라 안전모 방향 표시이다.

## 변경 파일

- backend/app/schemas/api.py: 보정 요청 스키마.
- backend/app/routers/devices.py: POST /api/devices/{device_id}/heading-calibration. 최신 IMU 값 확인, 앵커 벽 방향 계산, 보정값 저장.
- backend/app/services/device_service.py: IMU 수신시각, 보정값 보존.
- backend/app/services/serializers.py: heading_deg / heading_at / heading_calibrated_at 전달.
- frontend/src/types/index.ts, services/api.ts: 방향 데이터와 보정 API.
- frontend/src/App.tsx, components/SiteMap.tsx, styles.css: 지도 방향 표시·보정 UI.

프런트엔드 빌드 성공. 서버 재시작 후 실제 웹 보정과 180도 표시 확인. 기존 P4 펌웨어가 yaw를 보내므로 이번 기능은 P4 재플래시 없이 적용됐다. 실제 90도 회전량·장착 축 정확도는 실물 비교 필요.
