# 2026-10-16 실물 재연결 점검

- 서버 8000, 웹 5174 정상. PC Wi-Fi WISET_5G, IPv4 192.168.0.40.
- 사용자 전원 투입 후 COM25 P4와 COM6 UWB 태그를 각각 확인.
- P4 UART: Wi-Fi AIHSLab2 접속 실패 반복(reason=201), 서버 192.168.0.223:8000 Host unreachable. 현재 PC 환경과 불일치.
- P4 마이크 PCM peak와 BNO085 yaw/pitch/roll 출력 확인. 이 사실은 STT/통화/음성 출력 성공을 의미하지 않는다.
- UWB 태그 USB: 앵커 1~4 거리 관측 모두 valid. 표본 약 2.42/4.02/2.82/3.77m. 정확도나 지도 좌표 정상은 아직 검증하지 않음.
- 서버 카메라 수신/분석 0프레임. UWB와 P4 서버 last_seen은 10/10 값. 화면의 기존 값은 현재 측정값 아님.
- P4 16MiB 전체 플래시 로컬 백업 완료: C:/dev/hanmir-runtime/p4-before-network-fix-20261016.bin (비밀정보 포함 가능, 업로드 금지).
- UWB 백업 중 COM6 연결 끊김, 미완료. 부분 파일을 복원용 정상 백업으로 사용하지 않는다.
- 이후 COM25/COM6 모두 사라짐. Windows PresentOnly에도 Bluetooth COM4/5만 확인됨.
- P4 stage 기존 main/sdkconfig 별도 로컬 압축 백업 후 현재 저장소 main 동기화.
- 로컬 sdkconfig: WISET_2.4G, 서버192.168.0.40, 서버 로컬 카메라/통화 토큰 동기화. 비밀번호/토큰 출력·Git 저장 안 함.
- P4 빌드 성공: 0x1ce540 bytes, 앱 파티션 0x400000, 55% 여유. 업로드 미실행.
- UWB 소스/네트워크 설정은 ASCII stage에 준비. 사용자명 한글 경로로 컴파일 실패하여 PLATFORMIO_CORE_DIR=C:/pio-core로 재빌드 진행.
- 다음: USB 인식 복구 → UWB 백업 재시도 → 각 펌웨어 업로드 → 실제 heartbeat/camera/UWB 재수신 → 스피커/음성/방향 기능 시험.
- 앵커 펌웨어/현장 XY/위험 임계값은 이번 연결 작업에서 변경하지 않음.
