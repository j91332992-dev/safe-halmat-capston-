#include "config.h"
#include "app_modules.h"

bool speakerBegin() {
  pinMode(LOCAL_ALERT_PIN, OUTPUT);
  Serial.printf("[SPEAKER] MAX98357A I2S 구성 BCLK=%d WS=%d DATA=%d\n", I2S_SPK_BCLK, I2S_SPK_WS, I2S_SPK_DATA);
  return true;
}

void speakerPlayTone(uint16_t frequency, uint16_t durationMs) {
  Serial.printf("[SPEAKER] 경고음 출력 freq=%u duration=%u\n", frequency, durationMs);
  tone(LOCAL_ALERT_PIN, frequency, durationMs);
}

void speakerPlayAlert(uint8_t repeats) {
  for (uint8_t i = 0; i < repeats; ++i) {
    speakerPlayTone(1400, 220);
    delay(280);
  }
}

void speakerStop() {
  noTone(LOCAL_ALERT_PIN);
  Serial.println("[SPEAKER] 출력 중지");
}

