# UWB 수동 X·Y 지도 방식 롤백 — 2026-10-10

## 요청 및 변경

사용자 요청으로 시작 시 10초 앵커 간 자동 측량과 지도 생성을 제거한다. 웹의 기존 작업장 설계에서 가로 X(m)·세로 Y(m)를 직접 입력하고 설계 저장 후 현장에 적용한다. 자동 측량 서버 API/계산 서비스, 웹 상태 패널/API 메서드, 앵커 survey 헤더와 연결 코드를 제거했다. anchor.cpp는 자동 측량 추가 전 HEAD 내용으로 복원하고 ASCII 빌드 staging에도 반영했다.

태그 거리 계산의 잘못된 시계 오프셋 부호 확장 제거, 파일 SQLite NullPool, P4·카메라·음성·방향 관련 개선은 유지했다. 자동 측량 원본 자료와 이전 진행 문서는 시행 기록으로 보관한다.

## 서버·웹

실행 서버를 재시작해 수동 지도 코드 반영. GET /api/layout 응답의 지도는 5.2×3.2m, 앵커 좌표는 1=(0,0), 2=(5.2,0), 3=(5.2,3.2), 4=(0,3.2), 높이 2.2m로 유지됐다. DB 지도/구역/출구/설계안을 임의 변경하지 않았다. 웹 기존 LayoutEditor의 가로 X·세로 Y 입력, 설계 저장, 현장에 적용 흐름을 복원했다. 실제 브라우저 화면 조작 검증이나 테스트 스위트는 실행하지 않았다.

## 장치 업데이트

자동 측량은 이미 네 앵커에 업로드됐으므로 서버 변경만으로 장치 측 측량을 없앨 수 없다. 앵커 1→2→3→4 순서로 USB를 연결해 일반 위치 측정 펌웨어를 재업로드해야 한다. 태그와 P4는 이번 롤백 재업로드 대상이 아니다. 1번 USB COM7/02E4F754 확인, 현재 롤백 펌웨어 빌드 및 업로드 진행 중. 완료 내역은 아래에 추가한다.

빌드 근거: C:\dev\hanmir-runtime\anchor-manual-rollback-build-20261010.log
서버 로그: C:\dev\hanmir-runtime\backend-manual-map-20261010.*.log

### 앵커 1번 완료

COM7/02E4F754 확인 후 일반 anchor-01 앱(286032바이트)을 0x10000에 업로드했다. esptool 해시 검증 성공 및 하드 리셋 완료. 근거: C:/dev/hanmir-runtime/anchor-01-manual-rollback-upload-20261010.log. 2·3·4번 업로드는 아직 남아 있다.

### 앵커 2번 완료

COM8/02E4F75D 확인 후 일반 anchor-02 앱(285776바이트)을 0x10000에 업로드했다. esptool 해시 검증 성공 및 하드 리셋 완료. UART 원본은 C:/dev/hanmir-runtime/anchor-02-manual-rollback-boot-20261010.log에 저장했다. 1·2번 완료, 3·4번 업로드가 남았다. 업로드 근거: C:/dev/hanmir-runtime/anchor-02-manual-rollback-upload-20261010.log.

### 앵커 3번 완료

COM9/02E4F8D0 확인 후 일반 anchor-03 앱(285776바이트)을 0x10000에 업로드했다. esptool 해시 검증 성공 및 하드 리셋 완료. UART 기록: C:/dev/hanmir-runtime/anchor-03-manual-rollback-boot-20261010.log. 1·2·3번 완료, 4번 업로드가 남았다. 업로드 근거: C:/dev/hanmir-runtime/anchor-03-manual-rollback-upload-20261010.log. 네 앵커 롤백 펌웨어 전체 빌드 성공(빌드 로그 확인).

### 앵커 4번 완료 및 롤백 완료

COM10/02E4F8EE 확인 후 일반 anchor-04 앱(285776바이트)을 0x10000에 업로드했다. esptool 해시 검증 성공 및 하드 리셋 완료. 1·2·3·4번 전체 일반 위치 측정 펌웨어 반영 완료. UART 원본: C:/dev/hanmir-runtime/anchor-04-manual-rollback-boot-20261010.log. 업로드 근거: C:/dev/hanmir-runtime/anchor-04-manual-rollback-upload-20261010.log. 서버·웹의 자동 측량 기능 제거와 네 앵커 재업로드까지 완료했다. 웹에서 가로 X·세로 Y 입력 → 설계 저장 → 현장에 적용으로 사용한다.

### 웹 실행본 갱신 완료
사용자의 웹 롤백 요청 후 자동 측량 코드 참조가 없는 것을 재확인하고 npm run build(TypeScript 및 Vite) 성공. dist 실행 산출물 갱신. 기존 Vite PID 8616을 확인 후 종료하고 수동 지도 웹을 5174 포트에 재시작했다. HTTP 200 확인. 브라우저에서는 새로고침해 사용한다. 카메라/방향 등 자동 지도 추가 전에 진행한 기능은 유지했다.

### 지도 값 불일치 제보 확인
사용자 제보 후 실제 Chrome의 /layout 및 /map 화면과 서버 layout/draft, layout, dashboard/snapshot을 비교했다. 현재 사용자 저장 설계는 4.8×2.5m(13:38:59 KST 저장)이며 세 API와 실시간 지도 상단 모두 동일했다. 이전 5.2×3.2m 기록은 당시 값이며 현재값이 아니다. 오른쪽 현재 위치 X4.3/Y2.5m는 작업자 태그 좌표로 지도 크기와 다른 값이다. 자동 측량 참조는 제거된 상태이며 LayoutEditor/layout.py는 HEAD 대비 변경 없음. 사용자 입력값을 임의로 이전 치수로 덮어쓰지 않았다.
