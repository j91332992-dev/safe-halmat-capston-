#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include "config.h"
#include "app_modules.h"

static bool post(JsonDocument &doc, const char *path) {
  if (WiFi.status() != WL_CONNECTED) return false;
  HTTPClient http; http.begin(String(SERVER_BASE_URL) + path); http.addHeader("Content-Type", "application/json");
  String body; serializeJson(doc, body);
  int code = http.POST(body);
  if (code < 200 || code >= 300) Serial.printf("[SERVER][ERROR] %s code=%d body=%s\n", path, code, http.getString().c_str());
  http.end();
  return code >= 200 && code < 300;
}

static void common(JsonDocument &doc) {
  doc["organization_id"] = ORGANIZATION_ID; doc["site_id"] = SITE_ID; doc["worker_id"] = WORKER_ID;
  doc["helmet_id"] = HELMET_ID; doc["device_id"] = DEVICE_ID;
}

bool sendDistances(const UwbMeasurement *items, size_t count) {
  JsonDocument doc; common(doc); doc["uwb_tag_id"] = UWB_TAG_ID;
  JsonArray list = doc["measurements"].to<JsonArray>();
  for (size_t i = 0; i < count; ++i) {
    JsonObject row = list.add<JsonObject>();
    row["anchor_id"] = items[i].anchorId; row["distance_m"] = items[i].distanceM; row["quality"] = items[i].quality;
  }
  bool ok = post(doc, "/api/uwb/distances");
  Serial.printf("[UWB] 거리 데이터 전송 %s count=%u\n", ok ? "성공" : "실패", count);
  return ok;
}

bool sendPositionHeartbeat(const char *uwbStatus) {
  JsonDocument doc; common(doc);
  doc["rssi"] = WiFi.RSSI(); doc["battery"] = positionBatteryPercent(); doc["component_status"]["uwb"] = uwbStatus;
  bool ok = post(doc, "/api/devices/heartbeat");
  Serial.printf("[HEARTBEAT] 위치 태그 %s\n", ok ? "성공" : "실패");
  return ok;
}

