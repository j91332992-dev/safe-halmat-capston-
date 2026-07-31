#include "config.h"
#include "app_modules.h"

static bool lastRaw = HIGH;
static bool stable = HIGH;
static uint32_t changedAt = 0;
static uint32_t pressedAt = 0;
static uint32_t releasedAt = 0;
static uint8_t clicks = 0;

void buttonBegin() {
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  Serial.printf("[BUTTON] INPUT_PULLUP 핀=%d, 누르면 LOW\n", BUTTON_PIN);
}

void buttonLoop() {
  bool raw = digitalRead(BUTTON_PIN);
  if (raw != lastRaw) { lastRaw = raw; changedAt = millis(); }
  if (millis() - changedAt >= BUTTON_DEBOUNCE_MS && raw != stable) {
    stable = raw;
    if (stable == LOW) {
      pressedAt = millis();
      Serial.println("[BUTTON] 누름 감지");
    } else {
      uint32_t held = millis() - pressedAt;
      if (held >= LONG_PRESS_MS) {
        clicks = 0;
        serverSendButtonEvent("long_press");
      } else {
        ++clicks;
        releasedAt = millis();
      }
    }
  }
  if (clicks && millis() - releasedAt > MULTI_CLICK_WINDOW_MS) {
    String eventType = clicks >= 3 ? "triple_press" : clicks == 2 ? "double_press" : "single_press";
    Serial.printf("[BUTTON] 이벤트=%s\n", eventType.c_str());
    if (!serverSendButtonEvent(eventType) && eventType == "triple_press") speakerPlayAlert(5);
    clicks = 0;
  }
}

