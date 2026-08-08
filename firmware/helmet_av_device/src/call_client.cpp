#include <ArduinoJson.h>
#include <WebSocketsClient.h>

#include "config.h"
#include "app_modules.h"

static WebSocketsClient callSocket;
static volatile bool callActive = false;
static volatile bool callChannelConnected = false;
static TaskHandle_t callTaskHandle = nullptr;

static void stopCall() {
  if (!callActive) return;
  callActive = false;
  audioSetCallMode(false);
  speakerSetCallMode(false);
  Serial.println("[CALL] 관리자 통화 종료");
}

static void onCallSocket(WStype_t type, uint8_t *payload, size_t length) {
  if (type == WStype_CONNECTED) {
    callChannelConnected = true;
    Serial.println("[CALL] 보안 통화 채널 연결 성공");
    return;
  }
  if (type == WStype_DISCONNECTED) {
    callChannelConnected = false;
    stopCall();
    Serial.println("[CALL] 통화 채널 연결 끊김, 재연결 대기");
    return;
  }
  if (type == WStype_BIN) {
    if (callActive) speakerQueueCallPcm(payload, length);
    return;
  }
  if (type != WStype_TEXT) return;

  JsonDocument doc;
  if (deserializeJson(doc, payload, length)) return;
  const String messageType = doc["type"] | "";
  if (messageType == "call_start" && !callActive) {
    speakerSetCallMode(true);
    audioSetCallMode(true);
    callActive = true;
    Serial.println("[CALL] 관리자 양방향 통화 시작");
  } else if (messageType == "call_stop") {
    stopCall();
  }
}

static void pumpCallSocket() {
  callSocket.loop();
  if (!callActive || !callChannelConnected) return;

  uint8_t frame[AUDIO_CALL_FRAME_BYTES];
  for (uint8_t sent = 0; sent < 4; ++sent) {
    if (!audioReadCallFrame(frame, sizeof(frame))) break;
    if (!callSocket.sendBIN(frame, sizeof(frame))) break;
  }
}

static void callSocketTask(void *parameter) {
  for (;;) {
    pumpCallSocket();
    vTaskDelay(pdMS_TO_TICKS(2));
  }
}

void callBegin() {
  const String path = String("/ws/call/device/") + DEVICE_ID +
      "?token=" + CALL_DEVICE_TOKEN;
  callSocket.begin(SERVER_HOST, SERVER_PORT, path);
  callSocket.onEvent(onCallSocket);
  callSocket.setReconnectInterval(2000);
  callSocket.enableHeartbeat(15000, 3000, 2);
  const BaseType_t created = xTaskCreatePinnedToCore(
      callSocketTask, "call-ws", 6144, nullptr, 4, &callTaskHandle, 0);
  if (created == pdPASS) {
    Serial.println("[CALL] 보안 통화 채널 연결 준비, 전용 작업=OK");
  } else {
    callTaskHandle = nullptr;
    Serial.println("[CALL] 전용 작업 생성 실패, 메인 루프 모드");
  }
}

void callLoop() {
  if (callTaskHandle != nullptr) return;
  pumpCallSocket();

}
bool callIsActive() {
  return callActive;
}