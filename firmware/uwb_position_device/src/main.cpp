#include <Arduino.h>
#include "config.h"
#include "uwb_interface.h"
#include "app_modules.h"

static IUwbTag *uwb = nullptr;
static uint32_t lastSend = 0;
static uint32_t lastHeartbeat = 0;

void setup() {
  Serial.begin(115200);
  delay(800);
  Serial.println("\n[BOOT] 안전모 UWB 위치 태그 최종 통합 펌웨어 시작");
  positionWifiBegin();
  uwb = UWB_USE_MOCK ? createMockUwb() : createHardwareUwb();
  bool ready = uwb->begin();
  Serial.printf("[UWB] 초기화 %s mode=%s\n", ready ? "성공" : "실패", UWB_USE_MOCK ? "mock" : "hardware");
}

void loop() {
  positionWifiMaintain();
  if (millis() - lastSend >= SEND_INTERVAL_MS) {
    lastSend = millis();
    UwbMeasurement measurements[8];
    size_t count = uwb->measure(measurements, 8);
    if (count >= 3) {
      if (!sendDistances(measurements, count)) offlineQueuePush(measurements, count);
      else offlineQueueFlush();
    } else {
      Serial.printf("[UWB][ERROR] 유효 거리값 부족 count=%u\n", count);
    }
  }
  if (millis() - lastHeartbeat >= HEARTBEAT_INTERVAL_MS) {
    lastHeartbeat = millis();
    sendPositionHeartbeat(uwb->status());
  }
  delay(2);
}

