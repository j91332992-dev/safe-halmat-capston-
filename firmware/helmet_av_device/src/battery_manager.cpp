#include <Arduino.h>
#include "config.h"
#include "app_modules.h"

float batteryPercent() {
  // 실제 분압비에 맞게 보정 계수를 수정한다. ADC에 배터리 전압 직접 입력 금지.
  const float adc = analogRead(BATTERY_ADC_PIN);
  const float voltage = (adc / 4095.0f) * 3.3f * 2.0f;
  return constrain((voltage - 3.2f) / (4.2f - 3.2f) * 100.0f, 0.0f, 100.0f);
}

