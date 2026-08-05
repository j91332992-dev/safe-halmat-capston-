#include "config.h"
#include <Arduino.h>
#include <driver/i2s.h>

static bool speakerReady = false;
static uint8_t *speakerBuffer = NULL;
static size_t speakerBufferSize = 16000 * 2; // 1초 (약 32KB)

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

bool speakerBegin() {
  // I2S 스피커 설정 (MAX98357A, 16kHz, 16bit, mono)
  i2s_config_t i2s_speaker_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = 16000,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 1024,
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

  speakerReady = true;
  Serial.printf("[SPEAKER] MAX98357A I2S 초기화 성공 (I2S_NUM_1) BCLK=%d WS=%d DATA=%d\n", I2S_SPK_BCLK, I2S_SPK_WS, I2S_SPK_DATA);
  return true;
}

void speakerPlayTone(uint16_t frequency, uint16_t durationMs) {
  if (!speakerReady) {
    Serial.println("[SPEAKER] 스피커가 초기화되지 않음");
    return;
  }

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
}

void speakerPlayAlert(uint8_t repeats) {
  for (uint8_t i = 0; i < repeats; ++i) {
    speakerPlayTone(1400, 220);
    delay(280);
  }
}

void speakerStop() {
  if (!speakerReady) return;
  i2s_zero_dma_buffer(I2S_NUM_1);
  Serial.println("[SPEAKER] 출력 중지");
}
bool speakerIsReady() { return speakerReady; }
