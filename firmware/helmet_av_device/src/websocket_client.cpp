#include <ArduinoJson.h>
#include <WebSocketsClient.h>
#include "config.h"
#include "app_modules.h"

static WebSocketsClient socketClient;

static void onSocket(WStype_t type, uint8_t *payload, size_t length) {
  if (type == WStype_CONNECTED) {
    Serial.println("[WS] 서버 명령 채널 연결 성공");
  } else if (type == WStype_DISCONNECTED) {
    Serial.println("[WS][ERROR] 서버 명령 채널 연결 끊김");
  } else if (type == WStype_TEXT) {
    JsonDocument doc;
    if (deserializeJson(doc, payload, length)) return;
    String command = doc["command_type"] | "";
    Serial.printf("[WS] 명령 수신=%s\n", command.c_str());
    if (command == "play_alert") speakerPlayAlert();
    else if (command == "play_tone") speakerPlayTone();
    else if (command == "stop_alert") speakerStop();
    else if (command == "request_status") serverHeartbeat();
  }
}

void websocketBegin() {
  socketClient.begin(SERVER_HOST, SERVER_PORT, String("/ws/device/") + DEVICE_ID);
  socketClient.onEvent(onSocket);
  socketClient.setReconnectInterval(5000);
}

void websocketLoop() { socketClient.loop(); }

