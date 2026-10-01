#include "app_modules.h"

static UwbMeasurement pending[4];
static size_t pendingCount = 0;

void offlineQueuePush(const UwbMeasurement *items, size_t count) {
  pendingCount = min(count, (size_t)4);
  for (size_t i = 0; i < pendingCount; ++i) pending[i] = items[i];
  Serial.printf("[QUEUE] 최신 미전송 UWB 데이터 저장 count=%u\n", pendingCount);
}

void offlineQueueFlush() {
  if (!pendingCount) return;
  size_t count = pendingCount;
  pendingCount = 0;
  if (!sendDistances(pending, count)) pendingCount = count;
  else Serial.println("[QUEUE] 미전송 UWB 데이터 재전송 성공");
}

