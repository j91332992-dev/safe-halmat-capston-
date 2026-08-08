#include "config.h"
#include "app_modules.h"

// 카메라 HTTP 업로드와 무관하게 GPIO0을 독립 감시한다.
// BOOT 버튼을 눌렀다가 떼면 음성 녹음 요청 1회를 발생시킨다.
static portMUX_TYPE buttonMux = portMUX_INITIALIZER_UNLOCKED;
static volatile bool pressLogPending = false;
static volatile bool recordEventPending = false;
static volatile bool longEventPending = false;

static void buttonSamplerTask(void *parameter) {
  for (;;) {
    if (digitalRead(BUTTON_PIN) != LOW) {
      vTaskDelay(pdMS_TO_TICKS(10));
      continue;
    }

    vTaskDelay(pdMS_TO_TICKS(BUTTON_DEBOUNCE_MS));
    if (digitalRead(BUTTON_PIN) != LOW) continue;

    const uint32_t pressedAt = millis();
    portENTER_CRITICAL(&buttonMux);
    pressLogPending = true;
    portEXIT_CRITICAL(&buttonMux);

    // 해제될 때까지 이 전용 작업에서 기다린다. 메인 loop와 카메라는 계속 동작한다.
    while (digitalRead(BUTTON_PIN) == LOW) {
      vTaskDelay(pdMS_TO_TICKS(10));
    }
    const uint32_t held = millis() - pressedAt;

    portENTER_CRITICAL(&buttonMux);
    if (held >= LONG_PRESS_MS) longEventPending = true;
    else recordEventPending = true;
    portEXIT_CRITICAL(&buttonMux);

    vTaskDelay(pdMS_TO_TICKS(BUTTON_DEBOUNCE_MS));
  }
}

void buttonBegin() {
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  const BaseType_t created = xTaskCreatePinnedToCore(
      buttonSamplerTask, "button-sampler", 2048, nullptr, 1, nullptr, 0);
  Serial.printf("[BUTTON] 독립 감시 준비 핀=%d, 누르면 LOW, 현재=%d, task=%s\n",
                BUTTON_PIN, digitalRead(BUTTON_PIN), created == pdPASS ? "OK" : "FAIL");
}

void buttonLoop() {
  bool logPress = false;
  bool recordEvent = false;
  bool longEvent = false;
  portENTER_CRITICAL(&buttonMux);
  if (pressLogPending) {
    logPress = true;
    pressLogPending = false;
  }
  if (recordEventPending) {
    recordEvent = true;
    recordEventPending = false;
  }
  if (longEventPending) {
    longEvent = true;
    longEventPending = false;
  }
  portEXIT_CRITICAL(&buttonMux);

  if (logPress) Serial.println("[BUTTON] 누름 감지");
  if (longEvent) {
    Serial.println("[BUTTON] 이벤트=long_press");
    serverSendButtonEvent("long_press");
    return;
  }
  if (!recordEvent) return;

  Serial.println("[BUTTON] 이벤트=single_press");
  speakerPlayTone(1200, 120);
  speakerStop();
  delay(80);
  if (audioStartRecording()) {
    Serial.printf("[BUTTON] 녹음 시작 (%d초 후 자동 업로드)\n", AUDIO_RECORD_SECONDS);
  } else {
    Serial.println("[BUTTON] 녹음 시작 실패");
  }
}
