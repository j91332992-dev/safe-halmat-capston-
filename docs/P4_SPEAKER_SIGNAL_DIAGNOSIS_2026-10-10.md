# P4 스피커 무음: 출력 신호 분리 진단 — 2026-10-10

## 현재 결론
스피커 자체 고장으로 확정하지 않는다. GPIO20(BCLK)과 GPIO21(WS)이 독립적으로 동작하지 않는 현상을 실측 입력 및 펄스 카운터로 관측했다. 두 핀의 전기적 결합, 배선/납땜 연결, 앰프 쪽 영향, P4 쪽 문제를 구분하려면 앰프 연결을 분리한 상태의 비교가 필요하다. 본 계측은 멀티미터의 저항/전압 측정이나 외부 오실로스코프 파형 측정을 대신하지 않는다.

## 이전 비교
- 통화 수정 전 소스 df52167 전체 31개 파일 복원 후에도 무음. 당시 바이너리/설정과 비트 단위 동일한 비교는 아니다.
- 수정 후 상세 I2S 로그는 1000Hz/1500ms에 PCM 48,000바이트 전체 쓰기 성공. 실제 가청 출력은 없었다.
- 발견한 sdkconfig.before-wiset-20261010과 현재 설정의 HANMIR 마이크/스피커 항목 차이는 없다.
- 원래 플래시 백업에서 프로젝트 p4_record_play, 빌드 날짜 Oct 8 2026, ESP-IDF v5.5.5를 확인했다. 이는 별도 5초 큰 확인음 프로그램이므로 통합 펌웨어와 같은 것으로 취급하지 않았다.

## 전용 출력 비교
애플리케이션의 네트워크/카메라/마이크/IMU/배터리/통화 초기화를 호출하지 않고 직접 I2S를 구동했다. esp_hosted 라이브러리의 부팅 자동 초기화 로그는 존재한다. 이를 완전히 모든 라이브러리 작업이 없는 환경이라고 주장하지 않는다.

| 단계 | 출력 설정 | 기록된 PCM 쓰기 |
|---|---|---:|
| 1 | I2S1, 16bit mono left, 16kHz | 32,000 bytes |
| 2 | I2S1, 16bit mono right, 16kHz | 32,000 bytes |
| 3 | I2S1, 16bit stereo 같은 신호 양 채널, 16kHz | 64,000 bytes |
| 4 | I2S1, 32bit stereo 같은 신호 양 채널, 16kHz | 128,000 bytes |
| 5 | I2S0, 16bit stereo, 16kHz | 64,000 bytes |
| 6 | I2S1, 16bit stereo, 48kHz | 192,000 bytes |

사용자가 최초 하나 이상 들렸다고 응답한 후 바로 전부 안 들렸다고 정정했다. 최종 결과는 6개 모두 무음이다. 채널 선택이나 I2S 포트 변경으로 가청 출력이 복구됐다는 증거는 없다.

초기 진단 버퍼가 main task 스택을 초과하여 재부팅했다. static 버퍼로 수정한 뒤 위 6단계와 핀 교차 검사가 정상 완료됐다. 이 임시 진단 프로그램의 초기 오류를 기존 스피커 문제의 원인으로 혼동하지 않는다.

## 핀 교차 검사: 핵심 결과
I2S 채널을 삭제한 뒤 GPIO20/21/22를 reset하고, 시험하는 핀 하나만 INPUT_OUTPUT, 나머지는 INPUT+약한 pull-down으로 설정했다. LOW/HIGH를 20ms 유지하여 gpio_get_level로 읽었으며 각 핀에 100개 펄스를 생성했다. 펄스 카운터는 양의 에지 증가, 음의 에지 무시로 설정했다.

```text
DRIVE GPIO20 LOW=0,0,0 HIGH=1,1,0
DRIVE GPIO20 100 PULSES COUNTS=100,100,0
DRIVE GPIO21 LOW=0,0,0 HIGH=1,1,0
DRIVE GPIO21 100 PULSES COUNTS=100,100,0
DRIVE GPIO22 LOW=0,0,0 HIGH=0,0,1
DRIVE GPIO22 100 PULSES COUNTS=0,0,100
```

읽은 핀 순서는 항상 20,21,22다. GPIO20과21은 양방향으로 서로 따라갔고 GPIO22는 독립적이었다. 고속 I2S에서 WS 펄스가 설정상 예상과 다르게 관측된 것을 계기로 이 저속 검사를 실시했다. 출력 데이터가 두 핀에 분리되지 않는다면 앰프는 올바른 BCLK/WS를 얻지 못할 수 있다. 단락의 위치나 저항값은 아직 모른다.

## 필요한 다음 비교
1. 전체 전원을 끄고 MAX98357A BCLK/LRC 및 P4 GPIO20/21 연결부 사진 확인.
2. 앰프 쪽 BCLK와LRC 신호선을 분리 가능하면 분리한 뒤 동일 검사. 전원 상태에서 탈착하거나 임의로 공급 전원을 추가하지 않는다.
3. 분리 후 현상이 없어지면 앰프 또는 그 연결 쪽 영향. 유지되면 P4/남은 배선 쪽을 조사한다. 분리 위치에 따라 관측 범위가 달라진다.
4. MAX98357A VIN–GND 전압 및 SD_MODE 실제 상태는 아직 미측정이다. SPI/I2S 로그로 전압이나 앰프 활성화를 증명하지 않는다.

## 보관
- 진단 소스: firmware/diagnostics/p4_speaker_isolation/app_main.c 및 CMakeLists.txt. 평소 펌웨어에 자동 포함되지 않는다.
- 로컬 진단 바이너리: C:/dev/hanmir-runtime/p4-speaker-isolation-crosscheck.bin.
- 원시 로그: p4-speaker-isolation-crosscheck.log, p4-speaker-isolation-serial.log.
- 진단 후 통화 수정 전 일반 펌웨어로 복구 작업을 진행한다. 완료 여부는 후속 기록으로 확인한다.

## 참고
- MAX98357A 채널 및 데이터 형식: https://www.analog.com/en/products/max98357a.html
- ESP-IDF 5.5 ESP32-P4 I2S: https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32p4/api-reference/peripherals/i2s.html

## 독립 GPIO 검사 결과

I2S와 PCNT를 초기화하지 않는 gpio_only.c로 별도 빌드·업로드했다. 일반 GPIO 출력만 사용하고 핀 설정 덤프도 확인했다. 모든 핀의 GPIO Matrix SigOut ID는 256(simple GPIO output), 나머지 두 핀의 OutputEn은 0이었다. 두 차례 반복 모두 아래와 같았다.

```text
output=GPIO20 level=0 READ_20_21_22=0,0,0
output=GPIO20 level=1 READ_20_21_22=1,1,0
output=GPIO21 level=0 READ_20_21_22=0,0,0
output=GPIO21 level=1 READ_20_21_22=1,1,0
output=GPIO22 level=0 READ_20_21_22=0,0,0
output=GPIO22 level=1 READ_20_21_22=0,0,1
```

이 독립 비교는 I2S 형식/채널/PCNT 설정 때문에만 교차 현상이 생겼다는 설명을 지지하지 않는다. 연결된 상태의 디지털 레벨 관측이며, 저항 0옴의 단락으로 확정하지 않는다. 정확한 위치는 앰프 쪽 BCLK/LRC 분리 비교와 실제 전압·도통 측정이 필요하다. 사용자는 외관상 배선 문제가 없다고 답했으나 분리 비교나 사진은 아직 없다.

로그: C:/dev/hanmir-runtime/p4-pin-only-serial.log. 비교 바이너리도 로컬 보관했다. 진단 완료 후 통화 수정 전 일반 펌웨어 복구를 실행했다. 빌드 스테이지의 main/app_main.c 및 main/CMakeLists.txt도 일반 소스로 복원했다. build 폴더 바이너리는 마지막 진단 결과일 수 있으므로 후속 업로드 전에 반드시 정상 소스로 재빌드해야 한다.
