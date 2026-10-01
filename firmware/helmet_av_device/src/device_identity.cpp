#include <ArduinoJson.h>
#include "config.h"
#include "app_modules.h"

void identityBegin() {
  Serial.printf("[IDENTITY] org=%s site=%s worker=%s helmet=%s device=%s\n",
    ORGANIZATION_ID, SITE_ID, WORKER_ID, HELMET_ID, DEVICE_ID);
}

String identityJson() {
  JsonDocument doc;
  doc["organization_id"] = ORGANIZATION_ID;
  doc["site_id"] = SITE_ID;
  doc["worker_id"] = WORKER_ID;
  doc["helmet_id"] = HELMET_ID;
  doc["device_id"] = DEVICE_ID;
  String output;
  serializeJson(doc, output);
  return output;
}

