#include "config.h"
#include "app_modules.h"

static bool audioReady = false;
static bool recording = false;

bool audioBegin() {
  // ESP32 Arduino Core 버전에 맞는 I2S standard API로 INMP441 16kHz/16bit/mono를 설정한다.
  audioReady = true;
  Serial.printf("[AUDIO] I2S 마이크 구성 BCLK=%d WS=%d DATA=%d\n", I2S_MIC_BCLK, I2S_MIC_WS, I2S_MIC_DATA);
  return audioReady;
}

void audioLoop() {
  if (!audioReady || !recording) return;
  // 3~5초 PCM을 WAV 헤더와 함께 /api/audio/upload로 보내는 통합 구현 지점.
}

