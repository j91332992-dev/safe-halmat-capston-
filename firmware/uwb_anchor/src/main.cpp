#include <Arduino.h>
#include <SPI.h>
#include "config.h"

void setup() {
  Serial.begin(115200);
  delay(800);
  Serial.printf("\n[BOOT] UWB 앵커 통합 펌웨어 anchor_id=%s\n", ANCHOR_ID);
  SPI.begin(UWB_SPI_SCK, UWB_SPI_MISO, UWB_SPI_MOSI, UWB_SPI_CS);
  Serial.println("[UWB][CONFIG] 채택한 DW3000 라이브러리의 responder/TWR 초기화를 이 파일에 연결하세요.");
  Serial.println("[DIAG] 5V USB 전원, 전원 LED, anchor_id, 고정 좌표를 관리자 웹에서 확인하세요.");
}

void loop() {
  // 실제 DW3000 responder 수신/응답 루프. 앵커는 고정 좌표를 계산하지 않는다.
  static uint32_t lastLog = 0;
  if (millis() - lastLog > 5000) {
    lastLog = millis();
    Serial.printf("[ANCHOR] %s 동작 중 (adapter 연결 대기)\n", ANCHOR_ID);
  }
}

