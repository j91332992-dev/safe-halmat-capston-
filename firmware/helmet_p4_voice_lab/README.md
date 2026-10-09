# HANMIR 2.0 P4 음성 실험 프로젝트

DFR1172의 ESP32-P4에서 외장 INMP441을 단독으로 확인하는 ESP-IDF 실험 앱이다. 기존 S3 펌웨어와 서버 동작은 유지한다. 현재 준비 범위는 **I2S 마이크 입력 → ESP-SR AFE WebRTC 잡음 제거 → VAD 로그 → 처리된 PCM 녹음**이다. 맞춤형 한국어 WakeNet 모델, C6 네트워크 업로드, 카메라 동시 실행은 실물 검증과 모델 확보 후 연결한다.

배선 기준은 [2026-10-01 P4 최종 배선표](../../docs/HARDWARE_REDESIGN_ESP32P4.md)다. 마이크 배정은 P2 `GPIO31`=BCLK, `GPIO34`=WS, `GPIO36`=DATA, `L/R`=GND(왼쪽 채널), `VDD`=3.3V다. 세 GPIO의 상태는 **[단위시험 필요]**이므로 아래 절차에서 실물 보드와 배선을 확인한 뒤 입력한다. 펌웨어 기본값 `-1`은 유지한다.

같은 배선표의 MAX98357A `GPIO20/21/22`(I2S1 TX), MAX17048 `GPIO32/33`(I2C1), BNO085 `GPIO23/51`(UART1)은 이 마이크 단독 실험 앱에서 사용하지 않는다. 기존 UWB 태그도 P4 데이터선에 연결하지 않는다.

## 준비

- ESP-IDF의 ESP32-P4 지원 환경과 Python `pyserial` (`backend/requirements.txt`에 포함).
- 첫 빌드 시 ESP-SR `2.5.5`가 컴포넌트 레지스트리에서 내려받아진다. 버전을 고정하여 재현 가능하게 했다.
- DFR1172, INMP441, 실물 보드의 핀맵과 전압을 확인한다. S3 GPIO를 그대로 사용하지 않는다.
- `idf.py`는 현재 개발 PC에서 PATH에 발견되지 않았다. 이 저장소에서 P4 빌드·플래시·마이크 실행은 아직 검증되지 않았다.

## 첫 마이크 실험

1. `idf.py set-target esp32p4`를 실행한다.
2. `idf.py menuconfig`의 **HANMIR P4 voice lab**에서 실물로 확인한 INMP441 BCLK=`31`, WS=`34`, DATA=`36`을 입력한다. 기본값 `-1`은 미확정을 뜻하며, 핀이 없으면 펌웨어가 I2S를 시작하지 않는다.
3. 처음에는 `Enable WakeNet`을 끄고, `ESP-SR WebRTC noise suppression`만 켠다.
4. `idf.py build`, `idf.py -p COM포트 flash monitor`를 실행한다.
5. 조용한 곳과 팬·기계음에서 `VAD state`, `mic_peak`, 내부 RAM/PSRAM 로그를 확인한다.

단어 인식률은 이 로그만으로 판정할 수 없다. 동일한 마이크 위치·화자·소음 조건에서 PCM을 녹음해 실제 STT와 호출어 모델을 평가해야 한다.

## PCM 파일로 저장

`menuconfig`에서 `Print AFE output as base64 PCM lines`를 켜고 다시 빌드한다. 모니터를 종료한 뒤 빠른 USB 콘솔 포트를 사용하여 다음처럼 저장한다.

```powershell
python firmware/helmet_p4_voice_lab/capture_serial.py --port COM12 --seconds 5 --out recordings/quiet_01.wav
```

이 옵션은 진단용이다. 콘솔 출력 때문에 실시간 처리 지연이 생길 수 있으므로 WakeNet/응답 지연 측정 때는 끈다. 같은 조건에서 NS를 켠 WAV와 끈 WAV를 모은다. 현재 프로그램은 외장 INMP441의 왼쪽 채널 32비트 I2S 슬롯 상위 16비트를 사용한다. 실제 신호 레벨·채널·배선을 검증해야 한다.

## WakeNet 모델

`Enable WakeNet`은 **모델 선택과 flash model 파티션 준비 후** 켠다. 이 실험 앱은 모델 감지만 로그로 표시하며, 미검증 모델 감지를 “투투스”나 긴급 신고로 해석하지 않는다. 한국어 `투투스`, `살려주세요`, `화재 발생` 등의 맞춤 모델과 false trigger 측정이 필요하다. P4에서도 비상 문구 감지는 일반 호출어 대기와 독립적으로 항상 활성화할 계획이다.

## 서버 연결 준비

서버의 `POST /api/audio/upload`는 기존 S3의 업로드를 그대로 받고, 미래 P4가 호출어를 로컬에서 검증한 뒤 명령 WAV만 올릴 때 `wake_detected=true` Form 필드를 지원한다. 빈 STT 결과는 실행되지 않는다. 이 실험 펌웨어에는 아직 C6 네트워크 업로드가 없다. 현재 P4가 없는 상태에서 실제 보드 통신·음성 동시 실행을 검증할 수 없기 때문이다.

실물 연결 뒤 확인할 순서: 마이크 핀과 3.3V → I2S 음질 → NS 전후 녹음 → VAD 누락/오작동 → 맞춤 `투투스` 모델 → 긴급어 모델 → C6 업로드 → 카메라·스피커 동시 부하. 스피커를 켠 상태에서 AEC를 쓰려면 출력 PCM을 AFE의 playback reference로 전달해야 한다.
