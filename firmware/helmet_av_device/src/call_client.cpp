#include <ArduinoJson.h>
#include <WebSocketsClient.h>

#include "config.h"
#include "app_modules.h"

static WebSocketsClient callSocket;
static volatile bool callActive = false;
static volatile bool callChannelConnected = false;
static volatile bool callRinging = false;
static TaskHandle_t callTaskHandle = nullptr;
static TaskHandle_t ringingTaskHandle = nullptr;

static void playCallConnectedTone() {
  // The manager answered: one compact confirmation chime.
  speakerPlayTone(1480, 180);
}

static void playCallEndedTone() {
  // A compact falling "hang-up" cue.
  speakerPlayTone(850, 75);
  delay(25);
  speakerPlayTone(430, 150);
}

static bool waitWhileRinging(uint32_t durationMs) {
  const uint32_t startedAt = millis();
  while (callRinging && !callActive && millis() - startedAt < durationMs) {
    vTaskDelay(pdMS_TO_TICKS(25));
  }
  return callRinging && !callActive;
}

static void playRingingCycle() {
  speakerPlayTone(1047, 100);
  if (!waitWhileRinging(35)) return;
  speakerPlayTone(1319, 100);
  if (!waitWhileRinging(35)) return;
  speakerPlayTone(1568, 180);
}

static void ringingTask(void *parameter) {
  (void)parameter;
  for (;;) {
    if (!callRinging || callActive) {
      vTaskDelay(pdMS_TO_TICKS(40));
      continue;
    }
    playRingingCycle();
    waitWhileRinging(1100);
  }
}

void callStartRinging() {
  if (callActive) return;
  callRinging = true;
  Serial.println("[CALL] 관리자 응답 대기 컬러링 시작");
}

void callStopRinging() {
  const bool wasRinging = callRinging;
  callRinging = false;
  if (wasRinging && !callActive) speakerStop();
  if (wasRinging) Serial.println("[CALL] 관리자 응답 대기 컬러링 종료");
}

static void stopCall() {
  if (!callActive) return;
  callActive = false;
  audioSetCallMode(false);
  speakerSetCallMode(false);
  playCallEndedTone();
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
    callStopRinging();
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
    callStopRinging();
    delay(50);
    // Play one answer cue before full-duplex mode so the helmet microphone
    // does not relay it back to the operator.
    playCallConnectedTone();
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
  if (xTaskCreatePinnedToCore(
          ringingTask, "call-ringing", 3072, nullptr, 2,
          &ringingTaskHandle, 1) != pdPASS) {
    ringingTaskHandle = nullptr;
    Serial.println("[CALL][ERROR] 컬러링 작업 생성 실패");
  }
}

void callLoop() {
  if (callTaskHandle != nullptr) return;
  pumpCallSocket();

}
bool callIsActive() {
  return callActive;
}
