#pragma once
#include <Arduino.h>
#include "../src/uwb_interface.h"

bool positionWifiBegin();
void positionWifiMaintain();
bool sendDistances(const UwbMeasurement *items, size_t count);
bool sendPositionHeartbeat(const char *uwbStatus);
float positionBatteryPercent();
void offlineQueuePush(const UwbMeasurement *items, size_t count);
void offlineQueueFlush();

