#pragma once

// 실제 ESP32-S3-CAM 보드의 회로도와 핀맵을 확인한 뒤 반드시 수정한다.
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define SERVER_BASE_URL "http://192.168.0.10:8000"
#define SERVER_HOST "192.168.0.10"
#define SERVER_PORT 8000
#define OPERATION_MODE "hardware"

#define ORGANIZATION_ID "org-001"
#define SITE_ID "site-001"
#define WORKER_ID "worker-001"
#define HELMET_ID "helmet-001"
#define DEVICE_ID "helmet-001-av"

// 카메라 핀은 보드별 차이가 매우 커서 -1 상태에서는 실제 초기화를 막는다.
#define ENABLE_CAMERA_HARDWARE false
#define CAMERA_PIN_PWDN -1
#define CAMERA_PIN_RESET -1
#define CAMERA_PIN_XCLK -1
#define CAMERA_PIN_SIOD -1
#define CAMERA_PIN_SIOC -1
#define CAMERA_PIN_D7 -1
#define CAMERA_PIN_D6 -1
#define CAMERA_PIN_D5 -1
#define CAMERA_PIN_D4 -1
#define CAMERA_PIN_D3 -1
#define CAMERA_PIN_D2 -1
#define CAMERA_PIN_D1 -1
#define CAMERA_PIN_D0 -1
#define CAMERA_PIN_VSYNC -1
#define CAMERA_PIN_HREF -1
#define CAMERA_PIN_PCLK -1

// 아래는 충돌 검토용 추천 시작값이다. 카메라 핀과 중복되면 바꾼다.
#define I2S_MIC_BCLK 4
#define I2S_MIC_WS 5
#define I2S_MIC_DATA 6
#define I2S_SPK_BCLK 15
#define I2S_SPK_WS 16
#define I2S_SPK_DATA 17
#define BUTTON_PIN 18
#define BATTERY_ADC_PIN 7
#define LOCAL_ALERT_PIN 21

#define HEARTBEAT_INTERVAL_MS 5000
#define CAMERA_INTERVAL_MS 1000
#define BUTTON_DEBOUNCE_MS 40
#define MULTI_CLICK_WINDOW_MS 450
#define LONG_PRESS_MS 1200

