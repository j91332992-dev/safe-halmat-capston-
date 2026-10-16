# 투투스 모델 P4 실행 실험

운영 안전모 펌웨어가 아니다. 마이크, 카메라, Wi-Fi, UWB, 스피커 기능을 포함하지 않는다.
운영 P4에 이 앱만 업로드하면 해당 기능은 실행되지 않는다.

## 목적

실제 학습된 29,336바이트 int8 모델의 TFLite Micro 연산 지원, 내부 resource variable 할당,
텐서 arena 사용량 및 100회 Invoke 처리시간을 확인한다.
합성 특징만 입력하므로 인식률, 발화 종료 후 응답시간, 연속 배경 오호출률을 측정하지 않는다.
현재 모델은 검증 미통과 pilot이다. 임계값을 낮춰 운영에 적용하지 않는다.

## 재현

ESP-IDF 5.5.5 환경에서 `idf.py build`로 빌드한다. 동시 운영 서버 부하를 줄이려면
configure 후 `ninja -C build -j 2`를 사용한다. esp-tflite-micro는 1.4.1로 고정한다.
sdkconfig.defaults는 연결된 P4 revision 1.0에 맞춘다.
128KiB arena는 실험용 예약 용량이며 실측 메모리 사용량이 아니다.

모델 SHA256: `42709ab464158d10ef48083269af60e06c1a9a433c946c46de9facb0d83c471d`

입력 int8 [1,3,40], scale 0.10196078568696976 / zero point -128.
출력 uint8 [1,1], scale 0.00390625 / zero point 0.
실제 음성 통합 시 학습에 사용한 동일한 microfrontend와 상태 유지가 필수다.
일반 MFCC 또는 기존 ESP-SR 특징을 이 입력에 직접 넣으면 안 된다.

실물 실행 및 정상 펌웨어 복구 기록 없이 P4 실행 성공으로 보고하지 않는다.

