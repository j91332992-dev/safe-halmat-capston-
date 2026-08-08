#include <WiFi.h>
#include "config.h"
#include "app_modules.h"

bool positionWifiBegin() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int i = 0; i < 30 && WiFi.status() != WL_CONNECTED; ++i) { delay(500); Serial.print("."); }
  bool ok = WiFi.status() == WL_CONNECTED;
  Serial.printf("\n[WIFI] 위치 태그 연결 %s IP=%s\n", ok ? "성공" : "실패", ok ? WiFi.localIP().toString().c_str() : "-");
  return ok;
}

void positionWifiMaintain() {
  static uint32_t retryAt = 0;
  if (WiFi.status() != WL_CONNECTED && millis() - retryAt > 10000) {
    retryAt = millis();
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  }
}

