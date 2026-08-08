#include "config.h"
#include "app_modules.h"
#include <Arduino.h>
#include <driver/i2s.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <cstring>
#include <freertos/queue.h>

static bool speakerReady = false;
static uint8_t *speakerBuffer = NULL;
static size_t speakerBufferSize = 16000 * 2; // 1초 (약 32KB)
static QueueHandle_t callSpeakerQueue = nullptr;
static TaskHandle_t callSpeakerTaskHandle = nullptr;
static volatile bool speakerCallMode = false;

// 톤 생성 (사인파)
void generateTone(uint8_t *buffer, size_t bufferSize, uint16_t frequency, uint16_t durationMs) {
  const int sampleRate = 16000;
  const int samples = (sampleRate * durationMs) / 1000;
  const int numSamples = (samples < bufferSize / 2) ? samples : bufferSize / 2;

  for (int i = 0; i < numSamples; i++) {
    float t = (float)i / sampleRate;
    float value = sin(2.0 * PI * frequency * t) * 0.5; // 볼륨 50%
    int16_t sample = (int16_t)(value * 32767);
    buffer[i * 2] = sample & 0xFF;
    buffer[i * 2 + 1] = (sample >> 8) & 0xFF;
  }
}

static void callSpeakerTask(void *parameter) {
  uint8_t frame[AUDIO_CALL_FRAME_BYTES];
  for (;;) {
    if (!speakerCallMode || !callSpeakerQueue) {
      vTaskDelay(pdMS_TO_TICKS(10));
      continue;
    }
    if (xQueueReceive(callSpeakerQueue, frame, pdMS_TO_TICKS(40)) != pdPASS) continue;
    size_t written = 0;
    const esp_err_t result = i2s_write(
        I2S_NUM_1, frame, sizeof(frame), &written, pdMS_TO_TICKS(80));
    if (result != ESP_OK || written != sizeof(frame)) {
      Serial.printf("[CALL][SPEAKER] PCM 출력 실패 err=%d written=%u\n", result, (unsigned)written);
    }
  }
}

bool speakerBegin() {
  // I2S 스피커 설정 (MAX98357A, 16kHz, 16bit, mono)
  i2s_config_t i2s_speaker_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = 16000,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = 160,
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0,
    .mclk_multiple = I2S_MCLK_MULTIPLE_256,
    .bits_per_chan = I2S_BITS_PER_CHAN_16BIT
  };

  i2s_pin_config_t i2s_speaker_pins = {
    .bck_io_num = I2S_SPK_BCLK,
    .ws_io_num = I2S_SPK_WS,
    .data_out_num = I2S_SPK_DATA,
    .data_in_num = I2S_PIN_NO_CHANGE
  };

  esp_err_t result = i2s_driver_install(I2S_NUM_1, &i2s_speaker_config, 0, NULL);
  if (result != ESP_OK) {
    Serial.printf("[SPEAKER] I2S 드라이버 설치 실패: %d\n", result);
    return false;
  }

  result = i2s_set_pin(I2S_NUM_1, &i2s_speaker_pins);
  if (result != ESP_OK) {
    Serial.printf("[SPEAKER] I2S 핀 설정 실패: %d\n", result);
    return false;
  }

  result = i2s_zero_dma_buffer(I2S_NUM_1);
  if (result != ESP_OK) {
    Serial.printf("[SPEAKER] DMA 버퍼 초기화 실패: %d\n", result);
    return false;
  }

  result = i2s_start(I2S_NUM_1);
  if (result != ESP_OK) {
    Serial.printf("[SPEAKER] I2S 시작 실패: %d\n", result);
    return false;
  }

  speakerBuffer = (uint8_t *)malloc(speakerBufferSize);
  if (speakerBuffer == NULL) {
    Serial.println("[SPEAKER] 버퍼 할당 실패");
    return false;
  }

callSpeakerQueue = xQueueCreate(AUDIO_CALL_QUEUE_FRAMES, AUDIO_CALL_FRAME_BYTES);
  if (!callSpeakerQueue || xTaskCreatePinnedToCore(
          callSpeakerTask, "call-speaker", 3072, nullptr, 3,
          &callSpeakerTaskHandle, 1) != pdPASS) {
    Serial.println("[SPEAKER] 통화 출력 큐/작업 생성 실패");
    return false;
  }

  speakerReady = true;  Serial.printf("[SPEAKER] MAX98357A I2S 초기화 성공 (I2S_NUM_1) BCLK=%d WS=%d DATA=%d\n", I2S_SPK_BCLK, I2S_SPK_WS, I2S_SPK_DATA);
  return true;
}

void speakerPlayTone(uint16_t frequency, uint16_t durationMs) {
  if (speakerCallMode) return;
  if (!speakerReady) {
    Serial.println("[SPEAKER] 스피커가 초기화되지 않음");
    return;
  }

  audioSetSuppressed(true);
  Serial.printf("[SPEAKER] 톤 출력 freq=%u duration=%u\n", frequency, durationMs);

  generateTone(speakerBuffer, speakerBufferSize, frequency, durationMs);

  const int sampleRate = 16000;
  const int samples = (sampleRate * durationMs) / 1000;
  const int numSamples = (samples < speakerBufferSize / 2) ? samples : speakerBufferSize / 2;
  const size_t bytesToSend = numSamples * 2;

  Serial.printf("[SPEAKER] 전송 준비: %d 샘플, %zu 바이트\n", numSamples, bytesToSend);

  // 첫 번째 샘플 값 확인 (디버깅)
  int16_t firstSample = (int16_t)((speakerBuffer[1] << 8) | speakerBuffer[0]);
  Serial.printf("[SPEAKER] 첫 샘플: %d\n", firstSample);

  size_t bytes_written;
  esp_err_t result = i2s_write(I2S_NUM_1, speakerBuffer, bytesToSend, &bytes_written, portMAX_DELAY);

  Serial.printf("[SPEAKER] I2S 결과: err=%d, written=%zu/%zu\n", result, bytes_written, bytesToSend);

  if (bytes_written != bytesToSend) {
    Serial.printf("[SPEAKER][ERROR] 전송 불완료: %zu 바이트 부족\n", bytesToSend - bytes_written);
  }
  audioSetSuppressed(false);
}

void speakerPlayAlert(uint8_t repeats) {
  for (uint8_t i = 0; i < repeats; ++i) {
    speakerPlayTone(1400, 220);
    delay(280);
  }
}

static uint16_t readLe16(const uint8_t *data) {
  return (uint16_t)data[0] | ((uint16_t)data[1] << 8);
}

static uint32_t readLe32(const uint8_t *data) {
  return (uint32_t)data[0] | ((uint32_t)data[1] << 8) | ((uint32_t)data[2] << 16) | ((uint32_t)data[3] << 24);
}

bool speakerPlayAudioUrl(const String &audioUrl) {
  if (speakerCallMode) return false;
  if (!speakerReady || WiFi.status() != WL_CONNECTED || audioUrl.length() == 0) {
    Serial.println("[SPEAKER][ERROR] 음성 재생 준비 실패");
    return false;
  }
  String url = audioUrl;
  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    if (!url.startsWith("/")) url = "/" + url;
    url = String("http://") + SERVER_HOST + ":" + String(SERVER_PORT) + url;
  }

  HTTPClient http;
  http.setConnectTimeout(5000);
  http.setTimeout(10000);
  if (!http.begin(url)) return false;
  int status = http.GET();
  if (status != HTTP_CODE_OK) {
    Serial.printf("[SPEAKER][ERROR] TTS 다운로드 HTTP %d\n", status);
    http.end();
    return false;
  }

  WiFiClient *stream = http.getStreamPtr();
  uint8_t header[44];
  size_t headerRead = stream->readBytes(header, sizeof(header));
  bool valid = headerRead == sizeof(header)
    && memcmp(header, "RIFF", 4) == 0
    && memcmp(header + 8, "WAVE", 4) == 0
    && memcmp(header + 12, "fmt ", 4) == 0
    && memcmp(header + 36, "data", 4) == 0;
  if (!valid) {
    Serial.println("[SPEAKER][ERROR] 지원하지 않는 WAV 헤더");
    http.end();
    return false;
  }

  uint16_t format = readLe16(header + 20);
  uint16_t channels = readLe16(header + 22);
  uint32_t sampleRate = readLe32(header + 24);
  uint16_t bits = readLe16(header + 34);
  uint32_t remaining = readLe32(header + 40);
  if (format != 1 || channels != 1 || bits != 16 || sampleRate < 8000 || sampleRate > 48000) {
    Serial.printf("[SPEAKER][ERROR] WAV 형식 불일치 format=%u channels=%u rate=%lu bits=%u\n",
                  format, channels, (unsigned long)sampleRate, bits);
    http.end();
    return false;
  }

  audioSetSuppressed(true);
  i2s_zero_dma_buffer(I2S_NUM_1);
  i2s_set_clk(I2S_NUM_1, sampleRate, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_MONO);
  uint8_t buffer[1024];
  Serial.printf("[SPEAKER] 안전모 음성 재생 시작 rate=%lu bytes=%lu\n",
                (unsigned long)sampleRate, (unsigned long)remaining);

  bool ok = true;
  while (remaining > 0 && http.connected()) {
    size_t wanted = remaining < sizeof(buffer) ? remaining : sizeof(buffer);
    size_t received = stream->readBytes(buffer, wanted);
    if (received == 0) {
      ok = false;
      break;
    }
    size_t written = 0;
    esp_err_t result = i2s_write(I2S_NUM_1, buffer, received, &written, portMAX_DELAY);
    if (result != ESP_OK || written != received) {
      ok = false;
      break;
    }
    remaining -= received;
    delay(1);
  }

  i2s_set_clk(I2S_NUM_1, AUDIO_SAMPLE_RATE, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_MONO);
  i2s_zero_dma_buffer(I2S_NUM_1);
  http.end();
  audioSetSuppressed(false);
  Serial.printf("[SPEAKER] 안전모 음성 재생 %s\n", ok && remaining == 0 ? "완료" : "실패");
  return ok && remaining == 0;
}

bool speakerPlayPcm(const uint8_t *data, size_t length, uint32_t sampleRate) {
  if (speakerCallMode) return false;
  if (!speakerReady || data == nullptr || length == 0 || sampleRate == 0) return false;
  audioSetSuppressed(true);
  i2s_zero_dma_buffer(I2S_NUM_1);
  if (i2s_set_clk(I2S_NUM_1, sampleRate, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_MONO) != ESP_OK) {
    audioSetSuppressed(false);
    return false;
  }

  size_t offset = 0;
  bool ok = true;
  while (offset < length) {
    const size_t chunk = (length - offset) > 1024 ? 1024 : (length - offset);
    size_t written = 0;
    const esp_err_t result = i2s_write(I2S_NUM_1, data + offset, chunk, &written, portMAX_DELAY);
    if (result != ESP_OK || written != chunk) {
      ok = false;
      break;
    }
    offset += written;
  }

  const uint32_t playbackMs = (uint32_t)((length * 1000ULL) / (sampleRate * sizeof(int16_t)));
  delay(playbackMs + 100);
  i2s_zero_dma_buffer(I2S_NUM_1);
  i2s_set_clk(I2S_NUM_1, AUDIO_SAMPLE_RATE, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_MONO);
  audioSetSuppressed(false);
  Serial.printf("[SPEAKER] 녹음 재생 %s bytes=%u\n", ok ? "완료" : "실패", (unsigned)length);
  return ok;
}
void speakerStop() {
  if (!speakerReady) return;
  i2s_zero_dma_buffer(I2S_NUM_1);
  Serial.println("[SPEAKER] 출력 중지");
}
bool speakerIsReady() { return speakerReady; }
void speakerSetCallMode(bool enabled) {
  if (!speakerReady || !callSpeakerQueue) return;
  speakerCallMode = enabled;
  xQueueReset(callSpeakerQueue);
  i2s_zero_dma_buffer(I2S_NUM_1);
  i2s_set_clk(I2S_NUM_1, AUDIO_SAMPLE_RATE, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_MONO);
  Serial.printf("[CALL] 스피커 실시간 스트리밍 %s\n", enabled ? "시작" : "종료");
}

bool speakerQueueCallPcm(const uint8_t *data, size_t length) {
  if (!speakerCallMode || !callSpeakerQueue || !data || length == 0) return false;
  size_t offset = 0;
  while (offset < length) {
    uint8_t frame[AUDIO_CALL_FRAME_BYTES] = {0};
    const size_t remaining = length - offset;
    const size_t copied = remaining < sizeof(frame) ? remaining : sizeof(frame);
    memcpy(frame, data + offset, copied);
    if (xQueueSend(callSpeakerQueue, frame, 0) != pdPASS) {
      uint8_t dropped[AUDIO_CALL_FRAME_BYTES];
      xQueueReceive(callSpeakerQueue, dropped, 0);
      xQueueSend(callSpeakerQueue, frame, 0);
    }
    offset += copied;
  }
  return true;
}
