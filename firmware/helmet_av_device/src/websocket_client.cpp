#include <ArduinoJson.h>
#include <WebSocketsClient.h>
#include "config.h"
#include "app_modules.h"

static WebSocketsClient socketClient;
static TaskHandle_t socketTaskHandle = nullptr;

struct PlaybackRequest {
  String url;
  String commandId;
  bool listenAgain;
  bool startCallRinging;
};

static TaskHandle_t currentPlaybackTaskHandle = nullptr;

static void playbackTask(void *parameter) {
  PlaybackRequest *request = static_cast<PlaybackRequest *>(parameter);
  const bool played = speakerPlayAudioUrl(request->url);
  serverReportComponent("speaker", played ? "ok" : "error", request->commandId,
                        played ? "" : "audio playback failed");
  if (played && request->listenAgain) audioArmFollowup(AUDIO_FOLLOWUP_TIMEOUT_MS);
  if (request->startCallRinging) callStartRinging();
  delete request;
  currentPlaybackTaskHandle = nullptr;
  vTaskDelete(nullptr);
}

static void websocketTask(void *parameter) {
  (void)parameter;
  for (;;) {
    socketClient.loop();
    vTaskDelay(pdMS_TO_TICKS(2));
  }
}

static void onSocket(WStype_t type, uint8_t *payload, size_t length) {
  if (type == WStype_CONNECTED) {
    Serial.println("[WS] 서버 명령 채널 연결 성공");
  } else if (type == WStype_DISCONNECTED) {
    callStopRinging();
    Serial.println("[WS][ERROR] 서버 명령 채널 연결 끊김");
  } else if (type == WStype_TEXT) {
    JsonDocument doc;
    if (deserializeJson(doc, payload, length)) {
      Serial.println("[WS][ERROR] JSON 파싱 실패");
      return;
    }
    String command = doc["command_type"] | "";
    String commandId = doc["command_id"] | "";
    Serial.printf("[WS] 명령 수신='%s', length=%zu\n", command.c_str(), length);
    if (command == "play_alert") {
      if (currentPlaybackTaskHandle != nullptr) {
        speakerStop();
      }
      uint8_t repeats = doc["payload"]["repeats"] | 3;
      speakerPlayAlert(repeats);
      serverReportComponent("speaker", "ok", commandId);
    }
    else if (command == "play_audio") {
      String audioUrl = doc["payload"]["audio_url"] | "";
      Serial.printf("[WS] 안전모 음성 URL='%s'\n", audioUrl.c_str());
      if (currentPlaybackTaskHandle != nullptr) {
        Serial.println("[WS] 이전 음성 재생 즉시 중단 요청");
        speakerStop();
        for (int i = 0; i < 15 && currentPlaybackTaskHandle != nullptr; ++i) {
          vTaskDelay(pdMS_TO_TICKS(10));
        }
      }
      PlaybackRequest *request = new PlaybackRequest{
          audioUrl,
          commandId,
          doc["payload"]["listen_again"] | false,
          doc["payload"]["start_call_ringing"] | false};
      if (!request || xTaskCreatePinnedToCore(
              playbackTask, "tts-playback", 6144, request, 2, &currentPlaybackTaskHandle, 1) != pdPASS) {
        delete request;
        currentPlaybackTaskHandle = nullptr;
        Serial.println("[WS][ERROR] 비동기 음성 재생 작업 생성 실패");
      }
    }
    else if (command == "play_ack") {
      if (currentPlaybackTaskHandle != nullptr) {
        speakerStop();
      }
      Serial.println("[WS] 내장 호출 응답 재생");
      bool played = speakerPlayAcknowledgement();
      if (!played) played = speakerPlayTone(1200, 180);
      serverReportComponent("speaker", played ? "ok" : "error", commandId,
                            played ? "" : "acknowledgement playback failed");
      audioArmFollowup(AUDIO_FOLLOWUP_TIMEOUT_MS);
    }
    else if (command == "play_tone") {
      if (currentPlaybackTaskHandle != nullptr) {
        speakerStop();
      }
      uint16_t freq = doc["payload"]["frequency"] | 1200;
      uint16_t duration = doc["payload"]["duration"] | 300;
      const bool played = speakerPlayTone(freq, duration);
      serverReportComponent("speaker", played ? "ok" : "error", commandId,
                            played ? "" : "tone playback failed");
      if (doc["payload"]["listen_again"] | false) {
        audioArmFollowup(AUDIO_FOLLOWUP_TIMEOUT_MS);
      }
      if (doc["payload"]["start_call_ringing"] | false) callStartRinging();
    }
    else if (command == "start_call_ringing") callStartRinging();
    else if (command == "stop_call_ringing") callStopRinging();
    else if (command == "stop_alert") {
      if (currentPlaybackTaskHandle != nullptr) {
        speakerStop();
      }
      speakerStop();
    }
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
  const BaseType_t created = xTaskCreatePinnedToCore(
      websocketTask, "device-ws", 4096, nullptr, 2, &socketTaskHandle, 0);
  if (created != pdPASS) {
    socketTaskHandle = nullptr;
    Serial.println("[WS][ERROR] dedicated task creation failed; using main loop");
  }
}

void websocketLoop() {
  // Fallback only: normally the dedicated task keeps commands responsive even
  // while the main loop is blocked by camera or heartbeat HTTP requests.
  if (!socketTaskHandle) socketClient.loop();
}

