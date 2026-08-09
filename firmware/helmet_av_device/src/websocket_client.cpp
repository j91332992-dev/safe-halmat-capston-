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
    if (deserializeJson(doc, payload, length)) {
      Serial.println("[WS][ERROR] JSON 파싱 실패");
      return;
    }
    String command = doc["command_type"] | "";
    Serial.printf("[WS] 명령 수신='%s', length=%zu\n", command.c_str(), length);
    if (command == "play_alert") {
      uint8_t repeats = doc["payload"]["repeats"] | 3;
      speakerPlayAlert(repeats);
    }
    else if (command == "play_audio") {
      String audioUrl = doc["payload"]["audio_url"] | "";
      Serial.printf("[WS] 안전모 음성 URL='%s'\n", audioUrl.c_str());
      if (!speakerPlayAudioUrl(audioUrl)) {
        Serial.println("[WS][ERROR] 음성 재생 실패, 경고음으로 대체");
        speakerPlayAlert(3);
      }
    }
    else if (command == "play_ack") {
      Serial.println("[WS] 내장 호출 응답 재생");
      if (!speakerPlayAcknowledgement()) speakerPlayTone(1200, 180);
      audioArmFollowup(AUDIO_FOLLOWUP_TIMEOUT_MS);
    }
    else if (command == "play_tone") {
      uint16_t freq = doc["payload"]["frequency"] | 1200;
      uint16_t duration = doc["payload"]["duration"] | 300;
      speakerPlayTone(freq, duration);
    }
    else if (command == "stop_alert") speakerStop();
    else if (command == "record_audio") {
      Serial.println("[WS] audioStartRecording() 호출");
      audioStartRecording();
    }
    else if (command == "start_recording") {
      Serial.println("[WS] audioStartRecording() 호출");
      audioStartRecording();
    }
    else if (command == "stop_recording") {
      audioStopRecording();
      audioUpload();
    }
    else if (command == "request_status") serverHeartbeat();
  }
}

void websocketBegin() {
  socketClient.begin(SERVER_HOST, SERVER_PORT, String("/ws/device/") + DEVICE_ID);
  socketClient.onEvent(onSocket);
  socketClient.setReconnectInterval(5000);
}

void websocketLoop() { socketClient.loop(); }

