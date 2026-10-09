# MAX17048 단독 시험 — Arduino IDE 대안

ESP-IDF 설치가 끝나기 전에도 MAX17048 하드웨어를 검사할 수 있는 DFR1172(ESP32-P4)용 Arduino 스케치입니다. 이 스케치는 Wi-Fi, 카메라, 마이크, 스피커, 서버를 사용하지 않습니다.

> ESP-IDF v5.5.5 프로젝트와 같은 빌드 환경은 아닙니다. I2C 배선, 주소 `0x36`, 배터리 전압, SOC가 정상인지 빠르게 확인하기 위한 대안입니다.

## Arduino IDE 준비

1. Arduino IDE 2를 엽니다.
2. `File > Preferences > Additional boards manager URLs`에 아래 주소를 추가합니다.

   ```text
   https://espressif.github.io/arduino-esp32/package_esp32_index.json
   ```

3. `Tools > Board > Boards Manager`에서 `esp32` by Espressif Systems를 설치합니다.
4. `Tools > Board`에서 `FireBeetle 2 ESP32-P4`를 선택합니다. 보이지 않으면 `ESP32P4 Dev Module`을 선택합니다.
5. `Tools > Port`에서 DFR1172가 연결된 COM 포트를 선택합니다.
6. 이 폴더의 `max17048_arduino_test.ino`를 Arduino IDE에서 엽니다.

## 업로드와 시리얼 모니터

1. `Sketch > Upload`를 누릅니다.
2. 업로드가 끝나면 오른쪽 위 돋보기 모양의 **Serial Monitor**를 엽니다.
3. 속도를 `115200 baud`로 설정합니다.

정상이라면 다음처럼 출력됩니다.

```text
[MAX17048] I2C response: 0x36  <-- expected MAX17048
[MAX17048] Version register: 0x....
[MAX17048] BATTERY: voltage=4.021 V, SOC=82.4 %
```

`No response at 0x36`이 반복되면 MAX17048의 3.3V, 공통 GND, SDA=GPIO33, SCL=GPIO32, 배터리 JST를 확인합니다.
