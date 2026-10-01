#include <WiFi.h>
#include "config.h"
#include "app_modules.h"

bool wifiBeginAndWait() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("[WIFI] SSID=%s 연결 시도", WIFI_SSID);
  for (int i = 0; i < 30 && WiFi.status() != WL_CONNECTED; ++i) {
    delay(500);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WIFI] 연결 성공 IP=%s RSSI=%d\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
    return true;
  }
  Serial.println("\n[WIFI][ERROR] 연결 실패. SSID/PW와 2.4GHz 여부를 확인하세요.");
  return false;
}

void wifiMaintain() {
  static uint32_t lastRetry = 0;
  if (WiFi.status() == WL_CONNECTED || millis() - lastRetry < 10000) return;
  lastRetry = millis();
  Serial.println("[WIFI] 연결 복구 시도");
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

