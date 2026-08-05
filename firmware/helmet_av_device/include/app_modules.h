#pragma once
#include <Arduino.h>

void identityBegin();
String identityJson();
bool wifiBeginAndWait();
void wifiMaintain();
bool cameraBegin();
bool cameraUploadIfDue();
bool cameraIsReady();
bool audioBegin();
void audioLoop();
bool audioIsReady();
bool audioStartRecording();
void audioStopRecording();
bool audioUpload();
bool speakerBegin();
bool speakerIsReady();
void speakerPlayAlert(uint8_t repeats = 3);
void speakerPlayTone(uint16_t frequency = 1200, uint16_t durationMs = 300);
void speakerStop();
void buttonBegin();
void buttonLoop();
float batteryPercent();
bool serverRegister();
bool serverHeartbeat();
bool serverSendButtonEvent(const String &eventType);
void websocketBegin();
void websocketLoop();

