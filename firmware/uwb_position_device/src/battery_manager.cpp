#include <Arduino.h>
#include "config.h"
#include "app_modules.h"

float positionBatteryPercent() {
  float voltage = analogRead(BATTERY_ADC_PIN) / 4095.0f * 3.3f * 2.0f;
  return constrain((voltage - 3.2f) / 1.0f * 100.0f, 0.0f, 100.0f);
}

