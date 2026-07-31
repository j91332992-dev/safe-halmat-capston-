#include "config.h"
#include "app_modules.h"
#if ENABLE_CAMERA_HARDWARE
#include "esp_camera.h"
#endif

static bool cameraReady = false;
static uint32_t lastFrame = 0;

bool cameraBegin() {
#if ENABLE_CAMERA_HARDWARE
  camera_config_t c = {};
  c.pin_pwdn = CAMERA_PIN_PWDN; c.pin_reset = CAMERA_PIN_RESET;
  c.pin_xclk = CAMERA_PIN_XCLK; c.pin_sccb_sda = CAMERA_PIN_SIOD; c.pin_sccb_scl = CAMERA_PIN_SIOC;
  c.pin_d7 = CAMERA_PIN_D7; c.pin_d6 = CAMERA_PIN_D6; c.pin_d5 = CAMERA_PIN_D5; c.pin_d4 = CAMERA_PIN_D4;
  c.pin_d3 = CAMERA_PIN_D3; c.pin_d2 = CAMERA_PIN_D2; c.pin_d1 = CAMERA_PIN_D1; c.pin_d0 = CAMERA_PIN_D0;
  c.pin_vsync = CAMERA_PIN_VSYNC; c.pin_href = CAMERA_PIN_HREF; c.pin_pclk = CAMERA_PIN_PCLK;
  c.xclk_freq_hz = 20000000; c.ledc_timer = LEDC_TIMER_0; c.ledc_channel = LEDC_CHANNEL_0;
  c.pixel_format = PIXFORMAT_JPEG; c.frame_size = FRAMESIZE_QVGA; c.jpeg_quality = 12; c.fb_count = 2;
  cameraReady = esp_camera_init(&c) == ESP_OK;
#else
  cameraReady = false;
  Serial.println("[CAMERA][CONFIG] 실제 보드 핀맵 입력 후 ENABLE_CAMERA_HARDWARE=true로 변경하세요.");
#endif
  Serial.printf("[CAMERA] 초기화 %s\n", cameraReady ? "성공" : "대기/실패");
  return cameraReady;
}

bool cameraUploadIfDue() {
  if (!cameraReady || millis() - lastFrame < CAMERA_INTERVAL_MS) return false;
  lastFrame = millis();
  // 실제 JPEG POST 구현 지점: POST /api/camera/frame, multipart device_id/worker_id/file.
  Serial.println("[CAMERA] 프레임 캡처 주기 도달");
  return true;
}

