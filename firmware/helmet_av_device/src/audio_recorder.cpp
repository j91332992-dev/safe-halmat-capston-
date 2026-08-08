#include "config.h"
#include "app_modules.h"
#include <Arduino.h>
#include <driver/i2s.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <freertos/queue.h>
#include <esp32-hal-log.h>

static bool audioReady = false;
static volatile bool captureActive = false;
static volatile bool forceStartRequested = false;
static volatile bool forceStopRequested = false;
static volatile bool vadSuppressed = false;
static volatile uint32_t vadResumeAt = 0;

static const size_t frameSamples = (AUDIO_SAMPLE_RATE * AUDIO_VAD_FRAME_MS) / 1000;
static const size_t frameBytes = frameSamples * sizeof(int16_t);
static const size_t maxCaptureBytes = AUDIO_SAMPLE_RATE * sizeof(int16_t) * AUDIO_MAX_RECORD_SECONDS;
static const size_t preRollBytes = AUDIO_SAMPLE_RATE * sizeof(int16_t) * AUDIO_VAD_PRE_ROLL_MS / 1000;

static uint8_t *captureBuffer = nullptr;
static uint8_t *pendingBuffer = nullptr;
static uint8_t *preRollBuffer = nullptr;
static size_t captureBytes = 0;
static volatile size_t pendingBytes = 0;
static size_t preRollWrite = 0;
static size_t preRollCount = 0;
static TaskHandle_t vadTaskHandle = nullptr;
static portMUX_TYPE audioMux = portMUX_INITIALIZER_UNLOCKED;
static uint32_t lastUploadAttempt = 0;
static uint32_t lastHealthLog = 0;
static volatile uint32_t vadFramesRead = 0;
static volatile uint32_t vadLastLevel = 0;
static volatile uint32_t vadLastReadAt = 0;
static QueueHandle_t callMicQueue = nullptr;
static volatile bool callMode = false;

static bool suppressionIsActive() {
  if (vadSuppressed) return true;
  return (int32_t)(millis() - vadResumeAt) < 0;
}

static uint32_t calculateLevel(const int16_t *samples, size_t count) {
  if (count == 0) return 0;
  int64_t sum = 0;
  for (size_t i = 0; i < count; ++i) sum += samples[i];
  const int32_t dc = (int32_t)(sum / (int64_t)count);

  uint64_t absoluteSum = 0;
  for (size_t i = 0; i < count; ++i) {
    int32_t centered = (int32_t)samples[i] - dc;
    if (centered < 0) centered = -centered;
    absoluteSum += (uint32_t)centered;
  }
  return (uint32_t)(absoluteSum / count);
}

static void resetPreRoll() {
  preRollWrite = 0;
  preRollCount = 0;
}

static void appendPreRoll(const uint8_t *data, size_t length) {
  if (!preRollBuffer || preRollBytes == 0) return;
  for (size_t i = 0; i < length; ++i) {
    preRollBuffer[preRollWrite] = data[i];
    preRollWrite = (preRollWrite + 1) % preRollBytes;
    if (preRollCount < preRollBytes) ++preRollCount;
  }
}

static void copyPreRollToCapture() {
  captureBytes = 0;
  if (!preRollBuffer || preRollCount == 0) return;
  const size_t start = preRollCount == preRollBytes ? preRollWrite : 0;
  for (size_t i = 0; i < preRollCount && captureBytes < maxCaptureBytes; ++i) {
    captureBuffer[captureBytes++] = preRollBuffer[(start + i) % preRollBytes];
  }
}

static void appendCapture(const uint8_t *data, size_t length) {
  if (!captureBuffer || captureBytes >= maxCaptureBytes) return;
  const size_t remaining = maxCaptureBytes - captureBytes;
  const size_t copied = length < remaining ? length : remaining;
  memcpy(captureBuffer + captureBytes, data, copied);
  captureBytes += copied;
}

static void discardCapture(const char *reason) {
  if (captureActive) Serial.printf("[VAD] 녹음 취소: %s\n", reason);
  captureActive = false;
  captureBytes = 0;
}

static void finishCapture() {
  if (!captureActive) return;
  captureActive = false;

  const uint32_t durationMs = (uint32_t)((captureBytes * 1000ULL) /
      (AUDIO_SAMPLE_RATE * sizeof(int16_t)));
  if (durationMs < 350) {
    Serial.printf("[VAD] 너무 짧은 음성 폐기 duration=%lums\n", (unsigned long)durationMs);
    captureBytes = 0;
    return;
  }

  bool queued = false;
  portENTER_CRITICAL(&audioMux);
  if (pendingBytes == 0) {
    uint8_t *oldPending = pendingBuffer;
    pendingBuffer = captureBuffer;
    captureBuffer = oldPending;
    pendingBytes = captureBytes;
    queued = true;
  }
  portEXIT_CRITICAL(&audioMux);

  if (queued) {
    Serial.printf("[VAD] 발화 종료, 업로드 대기 duration=%lums bytes=%u\n",
                  (unsigned long)durationMs, (unsigned)captureBytes);
  } else {
    Serial.println("[VAD] 이전 음성 업로드 대기 중이라 이번 발화를 폐기합니다.");
  }
  captureBytes = 0;
}

static void startCaptureFromPreRoll(uint32_t level, uint32_t threshold, bool forced) {
  copyPreRollToCapture();
  captureActive = true;
  Serial.printf("[VAD] 발화 시작 mode=%s level=%lu threshold=%lu pre_roll=%ums\n",
                forced ? "manual" : "auto",
                (unsigned long)level,
                (unsigned long)threshold,
                AUDIO_VAD_PRE_ROLL_MS);
}

static void vadTask(void *parameter) {
  uint8_t frame[frameBytes];
  float noiseFloor = 80.0f;
  uint16_t voiceFrames = 0;
  uint16_t silentFrames = 0;
  const uint16_t silenceFramesNeeded =
      (AUDIO_VAD_END_SILENCE_MS + AUDIO_VAD_FRAME_MS - 1) / AUDIO_VAD_FRAME_MS;
  const uint32_t startedAt = millis();
  bool calibrationLogged = false;
  uint32_t lastLevelLog = 0;

  for (;;) {
    size_t bytesRead = 0;
    const esp_err_t result = i2s_read(
        I2S_NUM_0, frame, sizeof(frame), &bytesRead, portMAX_DELAY);
    if (result != ESP_OK || bytesRead < sizeof(int16_t)) {
      vTaskDelay(pdMS_TO_TICKS(5));
      continue;
    }

    const uint32_t now = millis();
    const uint32_t level = calculateLevel(
        reinterpret_cast<const int16_t *>(frame), bytesRead / sizeof(int16_t));
    vadLastLevel = level;
    vadLastReadAt = millis();
++vadFramesRead;

    if (callMode) {
      if (callMicQueue && xQueueSend(callMicQueue, frame, 0) != pdPASS) {
        uint8_t dropped[AUDIO_CALL_FRAME_BYTES];
        xQueueReceive(callMicQueue, dropped, 0);
        xQueueSend(callMicQueue, frame, 0);
      }
      continue;
    }

    if (suppressionIsActive()) {
      discardCapture("스피커 출력/대기 시간");
      voiceFrames = 0;
      silentFrames = 0;
      resetPreRoll();
      continue;
    }

    const bool calibrating = now - startedAt < AUDIO_VAD_CALIBRATION_MS;
    if (calibrating) {
      noiseFloor = noiseFloor * 0.92f + (float)level * 0.08f;
      appendPreRoll(frame, bytesRead);
      continue;
    }
    if (!calibrationLogged) {
      calibrationLogged = true;
      uint32_t threshold = (uint32_t)(noiseFloor * AUDIO_VAD_NOISE_MULTIPLIER);
      if (threshold < AUDIO_VAD_MIN_LEVEL) threshold = AUDIO_VAD_MIN_LEVEL;
      log_i("VAD_LISTENING noise=%lu threshold=%lu frame=%ums",
                    (unsigned long)noiseFloor, (unsigned long)threshold,
                    AUDIO_VAD_FRAME_MS);
    }

    uint32_t startThreshold = (uint32_t)(noiseFloor * AUDIO_VAD_NOISE_MULTIPLIER);
    if (startThreshold < AUDIO_VAD_MIN_LEVEL) startThreshold = AUDIO_VAD_MIN_LEVEL;
    uint32_t releaseThreshold = (uint32_t)(noiseFloor * AUDIO_VAD_RELEASE_MULTIPLIER);
    if (releaseThreshold < AUDIO_VAD_MIN_LEVEL) releaseThreshold = AUDIO_VAD_MIN_LEVEL;

    if (!captureActive && now - lastLevelLog >= 1000) {
      lastLevelLog = now;
      log_i("VAD_LEVEL current=%lu noise=%lu threshold=%lu",
                    (unsigned long)level,
                    (unsigned long)noiseFloor,
                    (unsigned long)startThreshold);
    }

    bool forceStart = false;
    bool forceStop = false;
    portENTER_CRITICAL(&audioMux);
    if (forceStartRequested) {
      forceStart = true;
      forceStartRequested = false;
    }
    if (forceStopRequested) {
      forceStop = true;
      forceStopRequested = false;
    }
    portEXIT_CRITICAL(&audioMux);

    if (!captureActive) {
      appendPreRoll(frame, bytesRead);
      if (forceStart) {
        startCaptureFromPreRoll(level, startThreshold, true);
        voiceFrames = 0;
        silentFrames = 0;
        continue;
      }

      if (level >= startThreshold) {
        if (voiceFrames < AUDIO_VAD_START_FRAMES) ++voiceFrames;
      } else {
        voiceFrames = 0;
        noiseFloor = noiseFloor * 0.995f + (float)level * 0.005f;
      }

      if (voiceFrames >= AUDIO_VAD_START_FRAMES) {
        startCaptureFromPreRoll(level, startThreshold, false);
        voiceFrames = 0;
        silentFrames = 0;
      }
      continue;
    }

    appendCapture(frame, bytesRead);
    if (forceStop) {
      finishCapture();
      silentFrames = 0;
      resetPreRoll();
      continue;
    }

    if (level >= releaseThreshold) {
      silentFrames = 0;
    } else if (silentFrames < silenceFramesNeeded) {
      ++silentFrames;
    }

    if (silentFrames >= silenceFramesNeeded || captureBytes >= maxCaptureBytes) {
      finishCapture();
      silentFrames = 0;
      resetPreRoll();
    }
  }
}

bool audioBegin() {
  i2s_config_t cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = AUDIO_SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = (int)frameSamples,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0,
    .mclk_multiple = I2S_MCLK_MULTIPLE_256,
    .bits_per_chan = I2S_BITS_PER_CHAN_16BIT
  };
  i2s_pin_config_t pins = {
    .bck_io_num = I2S_MIC_BCLK,
    .ws_io_num = I2S_MIC_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_MIC_DATA
  };

  if (i2s_driver_install(I2S_NUM_0, &cfg, 0, nullptr) != ESP_OK ||
      i2s_set_pin(I2S_NUM_0, &pins) != ESP_OK ||
      i2s_start(I2S_NUM_0) != ESP_OK) {
    Serial.println("[AUDIO] I2S 마이크 초기화 실패");
    return false;
  }

  captureBuffer = (uint8_t *)(psramFound() ? ps_malloc(maxCaptureBytes) : malloc(maxCaptureBytes));
  pendingBuffer = (uint8_t *)(psramFound() ? ps_malloc(maxCaptureBytes) : malloc(maxCaptureBytes));
  preRollBuffer = (uint8_t *)(psramFound() ? ps_malloc(preRollBytes) : malloc(preRollBytes));
  callMicQueue = xQueueCreate(AUDIO_CALL_QUEUE_FRAMES, AUDIO_CALL_FRAME_BYTES);
  if (!callMicQueue) {
    Serial.println("[AUDIO] 통화 마이크 큐 생성 실패");
    return false;
  }
  if (!captureBuffer || !pendingBuffer || !preRollBuffer) {
    Serial.println("[AUDIO] VAD 버퍼 할당 실패");
    return false;
  }

  audioReady = true;
  const BaseType_t created = xTaskCreatePinnedToCore(
      vadTask, "audio-vad", 4096, nullptr, 2, &vadTaskHandle, 1);
  if (created != pdPASS) {
    audioReady = false;
    Serial.println("[AUDIO] VAD 작업 생성 실패");
    return false;
  }

  Serial.printf("[AUDIO] INMP441 상시 VAD 준비 완료, 최대 %d초, task=OK, core=1\n",
                AUDIO_MAX_RECORD_SECONDS);
  return true;
}

static void createWavHeader(uint8_t *header, size_t dataSize) {
  const uint32_t byteRate = AUDIO_SAMPLE_RATE * 2;
  memcpy(header, "RIFF", 4);
  uint32_t size = dataSize + 36;
  memcpy(header + 4, &size, 4);
  memcpy(header + 8, "WAVEfmt ", 8);
  uint32_t fmtSize = 16;
  memcpy(header + 16, &fmtSize, 4);
  uint16_t format = 1, channels = 1, bits = 16, align = 2;
  memcpy(header + 20, &format, 2);
  memcpy(header + 22, &channels, 2);
  uint32_t rate = AUDIO_SAMPLE_RATE;
  memcpy(header + 24, &rate, 4);
  memcpy(header + 28, &byteRate, 4);
  memcpy(header + 32, &align, 2);
  memcpy(header + 34, &bits, 2);
  memcpy(header + 36, "data", 4);
  uint32_t data = dataSize;
  memcpy(header + 40, &data, 4);
}

bool audioStartRecording() {
  if (!audioReady || suppressionIsActive()) return false;
  portENTER_CRITICAL(&audioMux);
  forceStartRequested = true;
  portEXIT_CRITICAL(&audioMux);
  return true;
}

void audioStopRecording() {
  if (!audioReady) return;
  portENTER_CRITICAL(&audioMux);
  forceStopRequested = true;
  portEXIT_CRITICAL(&audioMux);
}

bool audioUpload() {
  if (!audioReady || WiFi.status() != WL_CONNECTED) return false;

  uint8_t *data = nullptr;
  size_t dataBytes = 0;
  portENTER_CRITICAL(&audioMux);
  data = pendingBuffer;
  dataBytes = pendingBytes;
  portEXIT_CRITICAL(&audioMux);
  if (!data || dataBytes == 0) return false;

  uint8_t wavHeader[44];
  createWavHeader(wavHeader, dataBytes);
  const String boundary = "----ESP32AudioBoundary";
  String head = "--" + boundary +
      "\r\nContent-Disposition: form-data; name=\"file\"; filename=\"audio.wav\"" +
      "\r\nContent-Type: audio/wav\r\n\r\n";
  String fields = "\r\n--" + boundary +
      "\r\nContent-Disposition: form-data; name=\"device_id\"\r\n\r\n" +
      String(DEVICE_ID) + "\r\n--" + boundary +
      "\r\nContent-Disposition: form-data; name=\"worker_id\"\r\n\r\n" +
      String(WORKER_ID) + "\r\n--" + boundary + "--\r\n";

  const size_t total = head.length() + sizeof(wavHeader) + dataBytes + fields.length();
  uint8_t *upload = (uint8_t *)(psramFound() ? ps_malloc(total) : malloc(total));
  if (!upload) {
    Serial.println("[AUDIO] 업로드 버퍼 할당 실패");
    return false;
  }

  size_t offset = 0;
  memcpy(upload + offset, head.c_str(), head.length());
  offset += head.length();
  memcpy(upload + offset, wavHeader, sizeof(wavHeader));
  offset += sizeof(wavHeader);
  memcpy(upload + offset, data, dataBytes);
  offset += dataBytes;
  memcpy(upload + offset, fields.c_str(), fields.length());

  HTTPClient http;
  http.setConnectTimeout(3000);
  http.setTimeout(12000);
  http.begin(String(SERVER_BASE_URL) + "/api/audio/upload");
  http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
  const int code = http.POST(upload, total);
  String response;
  if (code > 0) response = http.getString();
  if (response.length() > 300) response = response.substring(0, 300);
  Serial.printf("[AUDIO] 업로드 HTTP %d bytes=%u\n", code, (unsigned)dataBytes);
  if (response.length()) Serial.printf("[AUDIO] 서버 응답: %s\n", response.c_str());
  http.end();
  free(upload);

  portENTER_CRITICAL(&audioMux);
  if (pendingBuffer == data && pendingBytes == dataBytes) pendingBytes = 0;
  portEXIT_CRITICAL(&audioMux);
  return code >= 200 && code < 300;
}

void audioLoop() {
  if (millis() - lastHealthLog >= 2000) {
    lastHealthLog = millis();
    log_i("VAD_HEALTH ready=%d task=%d frames=%lu last_level=%lu last_read_ms=%lu listening=%d pending=%u",
                  audioReady ? 1 : 0,
                  vadTaskHandle != nullptr ? 1 : 0,
                  (unsigned long)vadFramesRead,
                  (unsigned long)vadLastLevel,
                  (unsigned long)vadLastReadAt,
                  audioIsListening() ? 1 : 0,
                  (unsigned)pendingBytes);
  }
  if (!audioReady || WiFi.status() != WL_CONNECTED) return;
  size_t queued = 0;
  portENTER_CRITICAL(&audioMux);
  queued = pendingBytes;
  portEXIT_CRITICAL(&audioMux);
  if (queued == 0 || millis() - lastUploadAttempt < 250) return;
  lastUploadAttempt = millis();
  audioUpload();
}

void audioSetSuppressed(bool suppressed) {
  portENTER_CRITICAL(&audioMux);
  vadSuppressed = suppressed;
  if (!suppressed) vadResumeAt = millis() + AUDIO_VAD_SPEAKER_COOLDOWN_MS;
  portEXIT_CRITICAL(&audioMux);
}

bool audioIsListening() {
  return audioReady && !suppressionIsActive();
}

bool audioIsReady() {
  return audioReady;
}
void audioSetCallMode(bool enabled) {
  callMode = enabled;
  if (callMicQueue) xQueueReset(callMicQueue);
  if (enabled) {
    discardCapture("실시간 통화 시작");
    pendingBytes = 0;
    resetPreRoll();
    Serial.println("[CALL] 마이크 실시간 스트리밍 시작");
  } else {
    vadResumeAt = millis() + AUDIO_VAD_SPEAKER_COOLDOWN_MS;
    Serial.println("[CALL] 마이크 스트리밍 종료, VAD 복귀");
  }
}

bool audioReadCallFrame(uint8_t *data, size_t capacity) {
  if (!callMode || !callMicQueue || !data || capacity < AUDIO_CALL_FRAME_BYTES) return false;
  return xQueueReceive(callMicQueue, data, 0) == pdPASS;
}
