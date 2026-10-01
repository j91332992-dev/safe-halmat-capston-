#include <Arduino.h>
#include "config.h"
#include "app_modules.h"

static uint32_t lastHeartbeat = 0;

void setup() {
#if !ENABLE_CAMERA_HARDWARE
  // Diagnostic: hold the shared camera XCLK / amplifier BCLK line LOW.
  // GPIO16 and GPIO17 remain untouched to avoid output contention.
  pinMode(CAMERA_PIN_XCLK, OUTPUT);
  digitalWrite(CAMERA_PIN_XCLK, LOW);
#endif

  Serial.begin(115200);
#if !ENABLE_CAMERA_HARDWARE
  delay(3000);
#else
  delay(800);
#endif
  Serial.println("\n[BOOT] 안전모 AV 최종 통합 펌웨어 시작");
  identityBegin();
  speakerBegin();
#if !ENABLE_CAMERA_HARDWARE
  delay(500);
  Serial.println("[DIAG][SPEAKER] 880Hz 시험음을 출력합니다.");
  speakerPlayTone(880, 1000);
  speakerStop();
  const bool micReady = audioBegin();
  delay(300);
  Serial.printf("[DIAG][MIC] 초기화 %s\n", micReady ? "성공" : "실패");
  speakerPlayTone(micReady ? 1800 : 400, 700);
  speakerStop();
  delay(500);
  Serial.println("[DIAG][MIC] 네트워크를 끄고 8초마다 자동 녹음합니다.");
  Serial.println("[DIAG] 짧은 신호음 직후 2초 동안 말하거나 손뼉을 치세요.");
  return;
#else
  audioBegin();
  cameraBegin();
#endif
  if (wifiBeginAndWait()) {
    serverRegister();
    websocketBegin();
    callBegin();
  }
  Serial.println("[DIAG] setup 완료. 부품 상태는 heartbeat와 관리자 진단 패널에서 확인하세요.");
}

void loop() {
#if !ENABLE_CAMERA_HARDWARE
  static uint32_t lastMicTest = 0;
  if (millis() - lastMicTest >= 8000) {
    lastMicTest = millis();
    speakerPlayTone(1400, 600);
    speakerStop();
    delay(250);
    Serial.println("[DIAG][MIC] 자동 녹음 시작");
    audioStartRecording();
    const uint32_t startedAt = millis();
    while (millis() - startedAt < 2300) {
      audioLoop();
      delay(1);
    }
  }
  delay(2);
  return;
#else
  wifiMaintain();
  audioLoop();
  if (audioConsumeFollowupTimeout()) {
    Serial.println("[VAD] 5초간 발화 없음, 호출 세션 종료");
    speakerPlayTone(900, 80);
    delay(35);
    speakerPlayTone(650, 110);
  }
  websocketLoop();
  callLoop();
  cameraUploadIfDue();
  if (millis() - lastHeartbeat >= HEARTBEAT_INTERVAL_MS) {
    lastHeartbeat = millis();
    serverHeartbeat();
  }
  delay(2);
#endif
}

