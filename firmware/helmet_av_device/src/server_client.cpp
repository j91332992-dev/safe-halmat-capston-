#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include "config.h"
#include "app_modules.h"

static bool postJson(const String &path, JsonDocument &doc) {
  if (WiFi.status() != WL_CONNECTED) return false;
  HTTPClient http;
  http.begin(String(SERVER_BASE_URL) + path);
  http.addHeader("Content-Type", "application/json");
  String body; serializeJson(doc, body);
  int code = http.POST(body);
  String response = http.getString();
  http.end();
  Serial.printf("[SERVER] POST %s code=%d\n", path.c_str(), code);
  if (code < 200 || code >= 300) Serial.printf("[SERVER][ERROR] %s\n", response.c_str());
  return code >= 200 && code < 300;
}

static void addCommon(JsonDocument &doc) {
  doc["organization_id"] = ORGANIZATION_ID; doc["site_id"] = SITE_ID;
  doc["worker_id"] = WORKER_ID; doc["helmet_id"] = HELMET_ID; doc["device_id"] = DEVICE_ID;
}

bool serverRegister() {
  JsonDocument doc; addCommon(doc);
  doc["device_type"] = "assistant_device"; doc["firmware_version"] = "0.1.0";
  doc["ip"] = WiFi.localIP().toString(); doc["mac"] = WiFi.macAddress();
  bool ok = postJson("/api/devices/register", doc);
  Serial.printf("[SERVER] 장치 등록 %s\n", ok ? "성공" : "실패");
  return ok;
}

bool serverHeartbeat() {
  JsonDocument doc; addCommon(doc);
  doc["rssi"] = WiFi.RSSI(); doc["battery"] = batteryPercent();
  JsonObject status = doc["component_status"].to<JsonObject>();
  status["camera"] = ENABLE_CAMERA_HARDWARE ? "ready" : "config_required";
  status["mic"] = "ready"; status["speaker"] = "ready"; status["button"] = "ready";
  bool ok = postJson("/api/devices/heartbeat", doc);
  Serial.printf("[HEARTBEAT] %s RSSI=%d battery=%.1f\n", ok ? "성공" : "실패", WiFi.RSSI(), batteryPercent());
  return ok;
}

bool serverSendButtonEvent(const String &eventType) {
  JsonDocument doc; addCommon(doc); doc["event_type"] = eventType;
  return postJson("/api/button-event", doc);
}

