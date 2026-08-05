#pragma once
#include "device_secrets.h"

#define OPERATION_MODE "hardware"
#define ORGANIZATION_ID "org-001"
#define SITE_ID "site-001"
#define WORKER_ID "worker-001"
#define HELMET_ID "helmet-001"
#define DEVICE_ID "helmet-001-av"

// 팀 카메라 보드(ESP32-S3 + OV5640)에서 확인한 핀맵
#define ENABLE_CAMERA_HARDWARE true
#define CAMERA_PIN_PWDN -1
#define CAMERA_PIN_RESET -1
#define CAMERA_PIN_XCLK 15
#define CAMERA_PIN_SIOD 4
#define CAMERA_PIN_SIOC 5
#define CAMERA_PIN_D7 16
#define CAMERA_PIN_D6 17
#define CAMERA_PIN_D5 18
#define CAMERA_PIN_D4 12
#define CAMERA_PIN_D3 10
#define CAMERA_PIN_D2 8
#define CAMERA_PIN_D1 9
#define CAMERA_PIN_D0 11
#define CAMERA_PIN_VSYNC 6
#define CAMERA_PIN_HREF 7
#define CAMERA_PIN_PCLK 13

#define I2S_MIC_BCLK 1
#define I2S_MIC_WS 2
#define I2S_MIC_DATA 42
#define I2S_SPK_BCLK 41
#define I2S_SPK_WS 40
#define I2S_SPK_DATA 39
#define BUTTON_PIN 0
// GPIO 7은 카메라 HREF와 겹치므로 배터리 ADC는 GPIO 3으로 분리
#define BATTERY_ADC_PIN 3

#define AUDIO_SAMPLE_RATE 16000
#define AUDIO_RECORD_SECONDS 2
#define HEARTBEAT_INTERVAL_MS 5000
#define CAMERA_INTERVAL_MS 3000
#define BUTTON_DEBOUNCE_MS 40
#define MULTI_CLICK_WINDOW_MS 450
#define LONG_PRESS_MS 1200