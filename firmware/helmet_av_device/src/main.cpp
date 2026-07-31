#include <Arduino.h>
#include "config.h"
#include "app_modules.h"

static uint32_t lastHeartbeat = 0;

void setup() {
  Serial.begin(115200);
  delay(800);
  Serial.println("\n[BOOT] 안전모 AV 최종 통합 펌웨어 시작");
  identityBegin();
  buttonBegin();
  speakerBegin();
  audioBegin();
  cameraBegin();
  if (wifiBeginAndWait()) {
    serverRegister();
    websocketBegin();
  }
  Serial.println("[DIAG] setup 완료. 부품 상태는 heartbeat와 관리자 진단 패널에서 확인하세요.");
}

void loop() {
  wifiMaintain();
  websocketLoop();
  buttonLoop();
  audioLoop();
  cameraUploadIfDue();
  if (millis() - lastHeartbeat >= HEARTBEAT_INTERVAL_MS) {
    lastHeartbeat = millis();
    serverHeartbeat();
  }
  delay(2);
}

