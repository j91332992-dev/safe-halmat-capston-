#include <Arduino.h>
#include "config.h"
#include "app_modules.h"
#if ENABLE_CAMERA_HARDWARE
#include "esp_camera.h"
#include <HTTPClient.h>
#include <WiFi.h>
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
  // OV5640 normally uses a 20 MHz XCLK.  The previous 10 MHz clock lengthened
  // exposure/readout and softened moving PPE edges.
  c.xclk_freq_hz = 20000000; c.ledc_timer = LEDC_TIMER_0; c.ledc_channel = LEDC_CHANNEL_0;
  // OV5640 + ESP32-S3 PSRAM 기준: VGA(640x480), 고화질 JPEG, 목표 8fps.
  // esp_camera의 JPEG 품질 값은 낮을수록 화질이 높다. 10은 전송량과 화질의 안정적인 상한이다.
  c.pixel_format = PIXFORMAT_JPEG; c.frame_size = FRAMESIZE_VGA; c.jpeg_quality = CAMERA_JPEG_QUALITY;
  if (psramFound()) {
    c.fb_location = CAMERA_FB_IN_PSRAM;
    c.fb_count = 2;
    c.grab_mode = CAMERA_GRAB_LATEST;
  } else {
    c.fb_location = CAMERA_FB_IN_DRAM;
    c.fb_count = 1;
    c.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  }
  cameraReady = esp_camera_init(&c) == ESP_OK;
  if (cameraReady) {
    // Preserve natural model input colors and add a small amount of sensor-side
    // edge detail. This adds no ESP32 frame post-processing or audio latency.
    sensor_t *sensor = esp_camera_sensor_get();
    if (sensor) {
      sensor->set_framesize(sensor, FRAMESIZE_VGA);
      sensor->set_quality(sensor, CAMERA_JPEG_QUALITY);
      sensor->set_brightness(sensor, 0);
      sensor->set_contrast(sensor, 1);
      sensor->set_saturation(sensor, 0);
      sensor->set_sharpness(sensor, 1);
      sensor->set_whitebal(sensor, 1);
      sensor->set_awb_gain(sensor, 1);
      sensor->set_exposure_ctrl(sensor, 1);
      sensor->set_gain_ctrl(sensor, 1);
      sensor->set_aec2(sensor, 1);
      sensor->set_dcw(sensor, 1);
      sensor->set_bpc(sensor, 1);
      sensor->set_wpc(sensor, 1);
    }
  }
#else
  cameraReady = false;
  Serial.println("[CAMERA][CONFIG] 실제 보드 핀맵 입력 후 ENABLE_CAMERA_HARDWARE=true로 변경하세요.");
#endif
  Serial.printf("[CAMERA] 초기화 %s\n", cameraReady ? "성공" : "대기/실패");
  return cameraReady;
}

bool cameraUploadIfDue() {
#if ENABLE_CAMERA_HARDWARE
  // Keep the normal 8 FPS stream for ambient speech and the initial wake clip.
  // During a call, retain exactly the low-rate source needed for 1 FPS YOLO.
  // The call WebSocket runs in its own priority-4 task, while this synchronous
  // camera request remains in the low-priority main loop and fails quickly.
  const bool callActive = audioIsCallMode();
  const bool voiceUploadBusy = audioShouldThrottleCamera();
  const uint32_t intervalMs = callActive
      ? CAMERA_CALL_INTERVAL_MS
      : (voiceUploadBusy ? CAMERA_VOICE_INTERVAL_MS : CAMERA_INTERVAL_MS);
  if (!cameraReady || millis() - lastFrame < intervalMs) return false;
  if (WiFi.status() != WL_CONNECTED) return false;

  // PSRAM에서는 CAMERA_GRAB_LATEST가 최신 프레임을 제공하므로 추가 캡처/폐기를 하지 않는다.
  // 이 호출 수를 한 번으로 유지해야 최신 프레임 주기를 안정적으로 맞출 수 있다.
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("[CAMERA] 캡처 실패");
    return false;
  }

  lastFrame = millis();
  HTTPClient http;
  String url = String(SERVER_BASE_URL) + "/api/camera/frame";
  http.begin(url);
  // A slow or failed camera request must never hold up wake-word audio for
  // several seconds. Drop this frame quickly and try a fresh one next time.
  http.setConnectTimeout(CAMERA_CONNECT_TIMEOUT_MS);
  http.setTimeout(CAMERA_RESPONSE_TIMEOUT_MS);

  String boundary = "----ESP32Boundary7MA4YWxkTrZu0gW";
  http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);

  String head = "--" + boundary + "\r\n" +
                "Content-Disposition: form-data; name=\"device_id\"\r\n\r\n" + DEVICE_ID + "\r\n" +
                "--" + boundary + "\r\n" +
                "Content-Disposition: form-data; name=\"worker_id\"\r\n\r\n" + WORKER_ID + "\r\n" +
                "--" + boundary + "\r\n" +
                "Content-Disposition: form-data; name=\"helmet_id\"\r\n\r\n" + HELMET_ID + "\r\n" +
                "--" + boundary + "\r\n" +
                "Content-Disposition: form-data; name=\"file\"; filename=\"frame.jpg\"\r\n" +
                "Content-Type: image/jpeg\r\n\r\n";

  String tail = "\r\n--" + boundary + "--\r\n";

  size_t totalLen = head.length() + fb->len + tail.length();
  uint8_t *buf = (uint8_t *)(psramFound() ? ps_malloc(totalLen) : malloc(totalLen));
  bool uploaded = false;
  if (buf) {
    memcpy(buf, head.c_str(), head.length());
    memcpy(buf + head.length(), fb->buf, fb->len);
    memcpy(buf + head.length() + fb->len, tail.c_str(), tail.length());

    int code = http.POST(buf, totalLen);
    uploaded = code >= 200 && code < 300;
    Serial.printf("[CAMERA] 캡처 전송 -> HTTP %d (크기: %u bytes)\n", code, fb->len);
    free(buf);
  } else {
    Serial.println("[CAMERA] 메모리 부족으로 업로드 취소");
  }

  esp_camera_fb_return(fb);
  http.end();
  return uploaded;
#else
  return false;
#endif
}

bool cameraIsReady() { return cameraReady; }
