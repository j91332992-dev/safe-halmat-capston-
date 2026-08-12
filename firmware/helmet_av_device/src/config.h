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
// 짧은 호출어(예: "투투스")의 첫 음절을 놓치지 않도록 한 프레임부터
// 발화를 시작한다. 대기 소음(약 10~20)보다 충분히 높은 최소값은 유지한다.
#define AUDIO_VAD_START_FRAMES 1
#define AUDIO_VAD_END_SILENCE_MS 500
#define AUDIO_VAD_CALIBRATION_MS 1500
// 실제 INMP441 현장 측정값에서 짧은 호출어의 피크가 50~60 부근까지
// 관찰되어, 기본 100 대신 45를 사용한다. 소음 바닥값의 배수도 함께 적용된다.
#define AUDIO_VAD_MIN_LEVEL 45
// 호출 안내음 뒤의 짧은 후속 명령 구간에서만 적용하는 낮은 감도다.
// 평상시 대기 감도는 위 값을 유지해 오작동을 줄인다.
// 후속 명령은 안내음 직후 짧게 말하는 경우가 많아 실제 측정된 저레벨
// 발화도 잡을 수 있도록 더 낮춘다. 이 값은 후속 대기 구간에만 적용된다.
#define AUDIO_FOLLOWUP_MIN_LEVEL 18
#define AUDIO_VAD_NOISE_MULTIPLIER 3.0f
#define AUDIO_VAD_RELEASE_MULTIPLIER 1.6f
#define AUDIO_VAD_SPEAKER_COOLDOWN_MS 80
// 안내음 직후 사용자가 자연스럽게 말할 수 있도록 7초를 제공한다.
// 서버 세션(12초)보다 짧게 유지해 만료 시점이 어긋나지 않게 한다.
// 안내음이 끝난 직후부터 후속 명령을 8초 동안 기다린다.
#define AUDIO_FOLLOWUP_TIMEOUT_MS 8000
#define HEARTBEAT_INTERVAL_MS 5000
#define CAMERA_TARGET_FPS 6
#define CAMERA_INTERVAL_MS (1000 / CAMERA_TARGET_FPS)
#define CAMERA_VOICE_INTERVAL_MS (1000 / 3)
#define CAMERA_CALL_INTERVAL_MS (1000 / 3)
#define CAMERA_CONNECT_TIMEOUT_MS 300
#define CAMERA_RESPONSE_TIMEOUT_MS 500
#define CAMERA_JPEG_QUALITY 10
#define BUTTON_DEBOUNCE_MS 40
#define MULTI_CLICK_WINDOW_MS 450
#define LONG_PRESS_MS 1200

