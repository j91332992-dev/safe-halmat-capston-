# P4 웹·앱 통화 연결 오류 수정

## 실제 원인

사용자는 웹과 Android 앱 모두에서 통화 연결 시 “마이크 권한 또는 서버 연결을 확인하세요” 표시를 보고했다.

- 서버 로그에는 PC 및 휴대폰의 `/api/calls/helmet-001-av/ticket` 요청이 모두 HTTP 409로 기록됐다.
- 서버는 안전모 통화 WebSocket이 없으면 “안전모 통화 채널이 오프라인입니다”로 거절한다. 장치 heartbeat가 online인 것과 통화 채널 online은 별개다.
- 기존 P4 펌웨어에는 마이크 STT 업로드와 TTS 재생이 있었지만 S3의 `call_client.cpp`에 해당하는 양방향 통화 구현이 없었다.
- 로컬 서버의 `CALL_DEVICE_TOKEN`도 설정되지 않아 장치 통화 인증을 통과할 수 없었다.
- 앱 `HelmetCall`은 저장된 PC 서버 주소 대신 WebView의 `https://localhost`에서 통화 WebSocket 주소를 만들고 있었다. 따라서 장치 통화 채널을 추가해도 앱에서 추가 연결 실패가 발생할 수 있었다.

## 수정한 코드

### P4

- `main/call_client.c` 신규: 인증된 전용 WebSocket `/ws/call/device/{device_id}`.
- 마이크의 기존 AFE 출력에서 16kHz mono PCM16을 공유한다. I2S RX 채널을 중복으로 열지 않는다.
- PCM을 최대 640바이트 단위로 전송하며 송수신 큐는 각각 6개로 제한한다. 오래된 PCM을 버려 통화 지연이 누적되지 않게 한다.
- 수신 PCM은 기존 MAX98357A I2S TX로 재생한다. 스피커 mutex로 TTS와 통화가 동시에 I2S를 조작하지 않게 한다.
- 통화 중 AI 발화 녹음·STT 업로드는 일시 중단한다. 종료하면 기존 AI 질문 경로로 돌아간다.
- 서버의 `call_start`/`call_stop` 및 연결 종료를 처리한다. `play_alert` 명령은 통화를 종료시킨 뒤 경고음을 출력한다.
- 마이크·스피커가 준비되지 않으면 통화 채널을 시작하지 않는다.
- `HANMIR_CALL_DEVICE_TOKEN`은 빈 기본값으로 정의했다. 실제 토큰은 로컬 sdkconfig에만 넣는다.

### 서버

- 기존 장치 토큰 인증을 유지한다. P4는 URL 대신 Authorization 헤더로 토큰을 전달하고 서버가 읽도록 추가했다.
- 장치가 보내는 `call_stop`을 처리하여 관리자에게 종료 상태를 알린다.
- 로컬 `.env`의 `CALL_DEVICE_TOKEN`과 P4 staging sdkconfig에 동일한 값을 설정했다. 값은 문서·GitHub에 올리지 않는다.

### 웹·앱

- `HelmetCall.tsx`: 공통 `getWsBaseUrl()`을 사용해 앱에 저장된 서버 주소로 통화한다.
- 통화 채널 오프라인, 로그인 만료, 마이크 권한 거부, 마이크 없음, 비보안 웹 주소를 구분해 표시한다.
- 통화에 실패하거나 상대가 바쁠 때 마이크 스트림과 AudioContext를 정리한다.
- 연결 확정 전에는 마이크 PCM을 보내지 않는다.
- HTTP LAN 주소로 접속한 일반 웹 브라우저에서는 마이크가 제한될 수 있다. PC 웹은 `http://localhost:5174`, 원격 웹의 마이크는 HTTPS 환경을 사용한다. 네이티브 앱은 앱 내부 WebView에서 마이크 권한을 사용한다.

## Android build13

- 파일: `releases/HanmirSafety-p4-mobile-v1.8-build13.apk`.
- GitHub Actions `38029735257`에서 빌드했다. TypeScript/Vite 및 Android/iOS 자산 동기화 완료.
- APK SHA-256: `47a0bba1c4b09cfc5b303a836d4e5ce560799eccf035a8b70d2768bc885ba1ab`.
- 인증서 SHA-256: `267e18f5d8ec2585c4b6a0b67abcd576f90635033ff9a0aba616960d6a49d974`.
- 최종 build12와 인증서가 같아 build12 위에 업데이트할 수 있다. 사용자는 직접 삭제 후 설치하는 방식을 선택했다.
- 앱 서버 설정: `http://192.168.0.40:8000`. 서버 재시작 후 로그인 세션은 다시 만들어야 한다.
- iOS 프로젝트는 build13으로 동기화했지만 신규 서명 IPA는 별도 Mac 환경에서 제작해야 한다.

## 실제 확인의 범위

P4 ESP-IDF 빌드 성공. 앱 크기 1,892,528바이트. COM25에서 앱 파티션 `0x10000`에 업로드하고 esptool 해시 일치 및 재부팅을 확인했다. 서버에 P4 `/ws/call/device/helmet-001-av`가 인증 후 등록됐다.

- `/api/calls/helmet-001-av/status`: HTTP 200, `channel_online=true`.
- `/api/calls/helmet-001-av/ticket`: 이전 HTTP 409에서 HTTP 200으로 변경, 통화 티켓 발급 확인.
- 동시에 원본 카메라 수신: frame_id 397, 조회 시 age_ms 31.
- 실제 두 방향 음성이 들리는지와 에코 상태는 사용자 확인 대기다. 컴파일 성공이나 연결 성공만으로 실제 양방향 음성이 검증됐다고 판단하지 않는다.
- 통화 상태 API의 `helmet_packets/bytes`, `operator_packets/bytes`는 해당 통화에서 서버에 도착한 PCM 계측이다. 패킷 수신만으로 스피커 재생 성공을 판단하지 않는다.
- 최종 서버 로그: `C:\dev\hanmir-runtime\backend-call-final.out.log`, `.err.log`; 펌웨어 빌드/업로드 로그: `p4-call-build.log`, `p4-call-upload.log`.

사용자는 앱/PC 마이크로 말한 내용이 안전모 스피커에서 들리는지, 안전모 마이크로 말한 내용이 앱/PC에서 들리는지를 각각 확인해야 한다. 통화 종료 후 AI 질문과 TTS가 복귀하는지도 확인한다.

현재 통화는 NS 처리된 마이크 PCM을 사용하지만 스피커 재생 신호를 참조하는 AEC는 구현하지 않았다. 실제 에코·하울링은 실물 배치와 음량 조건에서 확인해야 한다.
