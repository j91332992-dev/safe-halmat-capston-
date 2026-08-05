#include "config.h"
#include "app_modules.h"
#include <Arduino.h>
#include <driver/i2s.h>
#include <WiFi.h>
#include <HTTPClient.h>

static bool audioReady = false;
static bool recording = false;
static uint8_t *audioBuffer = nullptr;
static const size_t bufferSize = AUDIO_SAMPLE_RATE * 2 * AUDIO_RECORD_SECONDS;
static size_t recordedBytes = 0;

bool audioBegin() {
  i2s_config_t cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = AUDIO_SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 1024,
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
  if (i2s_driver_install(I2S_NUM_0, &cfg, 0, nullptr) != ESP_OK || i2s_set_pin(I2S_NUM_0, &pins) != ESP_OK || i2s_start(I2S_NUM_0) != ESP_OK) {
    Serial.println("[AUDIO] I2S 마이크 초기화 실패");
    return false;
  }
  audioBuffer = (uint8_t *)(psramFound() ? ps_malloc(bufferSize) : malloc(bufferSize));
  if (!audioBuffer) {
    Serial.println("[AUDIO] 녹음 버퍼 할당 실패");
    return false;
  }
  audioReady = true;
  Serial.printf("[AUDIO] INMP441 준비 완료, %d초 녹음, %u bytes\n", AUDIO_RECORD_SECONDS, (unsigned)bufferSize);
  return true;
}

static void createWavHeader(uint8_t *header, size_t dataSize) {
  const uint32_t byteRate = AUDIO_SAMPLE_RATE * 2;
  memcpy(header, "RIFF", 4); uint32_t size = dataSize + 36; memcpy(header + 4, &size, 4);
  memcpy(header + 8, "WAVEfmt ", 8); uint32_t fmtSize = 16; memcpy(header + 16, &fmtSize, 4);
  uint16_t format = 1, channels = 1, bits = 16, align = 2;
  memcpy(header + 20, &format, 2); memcpy(header + 22, &channels, 2);
  uint32_t rate = AUDIO_SAMPLE_RATE; memcpy(header + 24, &rate, 4); memcpy(header + 28, &byteRate, 4);
  memcpy(header + 32, &align, 2); memcpy(header + 34, &bits, 2);
  memcpy(header + 36, "data", 4); uint32_t data = dataSize; memcpy(header + 40, &data, 4);
}

bool audioStartRecording() {
  if (!audioReady || recording) return false;
  recordedBytes = 0;
  i2s_zero_dma_buffer(I2S_NUM_0);
  recording = true;
  Serial.println("[AUDIO] 녹음 시작");
  return true;
}

void audioStopRecording() {
  if (!audioReady) return;
  recording = false;
  Serial.printf("[AUDIO] 녹음 종료: %u bytes\n", (unsigned)recordedBytes);
}

bool audioUpload() {
  if (!audioReady || recordedBytes == 0 || WiFi.status() != WL_CONNECTED) return false;
  uint8_t wavHeader[44]; createWavHeader(wavHeader, recordedBytes);
  const String boundary = "----ESP32AudioBoundary";
  String head = "--" + boundary + "\r\nContent-Disposition: form-data; name=\"file\"; filename=\"audio.wav\"\r\nContent-Type: audio/wav\r\n\r\n";
  String fields = "\r\n--" + boundary + "\r\nContent-Disposition: form-data; name=\"device_id\"\r\n\r\n" + String(DEVICE_ID) + "\r\n" +
                  "--" + boundary + "\r\nContent-Disposition: form-data; name=\"worker_id\"\r\n\r\n" + String(WORKER_ID) + "\r\n" +
                  "--" + boundary + "--\r\n";
  size_t total = head.length() + sizeof(wavHeader) + recordedBytes + fields.length();
  uint8_t *upload = (uint8_t *)(psramFound() ? ps_malloc(total) : malloc(total));
  if (!upload) return false;
  size_t offset = 0;
  memcpy(upload + offset, head.c_str(), head.length()); offset += head.length();
  memcpy(upload + offset, wavHeader, sizeof(wavHeader)); offset += sizeof(wavHeader);
  memcpy(upload + offset, audioBuffer, recordedBytes); offset += recordedBytes;
  memcpy(upload + offset, fields.c_str(), fields.length());
  HTTPClient http;
  http.begin(String(SERVER_BASE_URL) + "/api/audio/upload");
  http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
  int code = http.POST(upload, total);
  Serial.printf("[AUDIO] 업로드 HTTP %d\n", code);
  http.end(); free(upload); recordedBytes = 0;
  return code >= 200 && code < 300;
}

void audioLoop() {
  if (!audioReady || !recording) return;
  size_t remaining = bufferSize - recordedBytes;
  size_t chunk = remaining < 1024 ? remaining : 1024;
  size_t bytesRead = 0;
  if (i2s_read(I2S_NUM_0, audioBuffer + recordedBytes, chunk, &bytesRead, portMAX_DELAY) == ESP_OK) recordedBytes += bytesRead;
  if (recordedBytes >= bufferSize) {audioStopRecording(); audioUpload();}
}
bool audioIsReady() { return audioReady; }
