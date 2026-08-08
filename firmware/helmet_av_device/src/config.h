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

// 2026-08-07 보고된 실제 납땜(마이크 4/5/6, 스피커 15/16/17)은
// 위 OV5640 카메라 핀과 충돌합니다. 전체 기능을 위해 아래 충돌 회피 핀으로
// 재배선하기 전에는 이 값을 실제 납땜값으로 단순 변경하지 마세요.
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
#define AUDIO_MAX_RECORD_SECONDS 5
#define AUDIO_VAD_FRAME_MS 20
#define AUDIO_CALL_FRAME_BYTES 640
#define AUDIO_CALL_QUEUE_FRAMES 8
#define AUDIO_VAD_PRE_ROLL_MS 300
#define AUDIO_VAD_START_FRAMES 2
#define AUDIO_VAD_END_SILENCE_MS 700
#define AUDIO_VAD_CALIBRATION_MS 1500
#define AUDIO_VAD_MIN_LEVEL 100
#define AUDIO_VAD_NOISE_MULTIPLIER 3.0f
#define AUDIO_VAD_RELEASE_MULTIPLIER 1.6f
#define AUDIO_VAD_SPEAKER_COOLDOWN_MS 700
#define HEARTBEAT_INTERVAL_MS 5000
#define CAMERA_TARGET_FPS 3
#define CAMERA_INTERVAL_MS (1000 / CAMERA_TARGET_FPS)
#define CAMERA_JPEG_QUALITY 10
#define BUTTON_DEBOUNCE_MS 40
#define MULTI_CLICK_WINDOW_MS 450
#define LONG_PRESS_MS 1200

