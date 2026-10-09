/*
 * HANMIR DFR1172 (ESP32-P4) MAX17048 standalone test for Arduino IDE.
 *
 * Wiring from the final wiring table:
 *   MAX17048 SDA -> DFR1172 P2 GPIO33
 *   MAX17048 SCL -> DFR1172 P2 GPIO32
 *   MAX17048 VIN/VDD -> DFR1172 3V3
 *   MAX17048 battery JST -> the battery B+ / B- line (SW6106 B+ / B-)
 */

#include <Wire.h>

constexpr int MAX17048_SDA_PIN = 33;
constexpr int MAX17048_SCL_PIN = 32;
constexpr uint8_t MAX17048_ADDR = 0x36;
constexpr uint32_t I2C_CLOCK_HZ = 100000;
constexpr uint32_t READ_INTERVAL_MS = 2000;

constexpr uint8_t MAX17048_REG_VCELL = 0x02;
constexpr uint8_t MAX17048_REG_SOC = 0x04;
constexpr uint8_t MAX17048_REG_VERSION = 0x08;

bool readRegister16(uint8_t reg, uint16_t &value) {
  Wire.beginTransmission(MAX17048_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }

  if (Wire.requestFrom(MAX17048_ADDR, static_cast<uint8_t>(2)) != 2) {
    return false;
  }

  value = (static_cast<uint16_t>(Wire.read()) << 8) | Wire.read();
  return true;
}

bool scanForMax17048() {
  bool found = false;
  Serial.println("[MAX17048] I2C1 scan start: SDA=GPIO33, SCL=GPIO32");

  for (uint8_t address = 0x08; address < 0x78; ++address) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() == 0) {
      Serial.printf("[MAX17048] I2C response: 0x%02X%s\n", address,
                    address == MAX17048_ADDR ? "  <-- expected MAX17048" : "");
      if (address == MAX17048_ADDR) {
        found = true;
      }
    }
  }

  if (!found) {
    Serial.println("[MAX17048][ERROR] No response at 0x36");
    Serial.println("[MAX17048][ERROR] Check 3.3V, common ground, SDA=GPIO33, SCL=GPIO32, and battery JST.");
  }
  return found;
}

void setup() {
  Serial.begin(115200);
  const uint32_t startedAt = millis();
  while (!Serial && millis() - startedAt < 3000) {
    delay(10);
  }

  Serial.println();
  Serial.println("[MAX17048] Standalone test started");
  Serial.println("[MAX17048] Wi-Fi, camera, microphone, speaker, and server are not used.");

  Wire.begin(MAX17048_SDA_PIN, MAX17048_SCL_PIN, I2C_CLOCK_HZ);

  while (!scanForMax17048()) {
    delay(READ_INTERVAL_MS);
  }

  uint16_t version = 0;
  if (readRegister16(MAX17048_REG_VERSION, version)) {
    Serial.printf("[MAX17048] Version register: 0x%04X\n", version);
  } else {
    Serial.println("[MAX17048][WARN] Version register read failed; continuing.");
  }
}

void loop() {
  uint16_t vcellRaw = 0;
  uint16_t socRaw = 0;
  const bool voltageOk = readRegister16(MAX17048_REG_VCELL, vcellRaw);
  const bool socOk = readRegister16(MAX17048_REG_SOC, socRaw);

  if (!voltageOk || !socOk) {
    Serial.printf("[MAX17048][ERROR] Read failed: VCELL=%s, SOC=%s\n",
                  voltageOk ? "OK" : "FAILED", socOk ? "OK" : "FAILED");
  } else {
    const float voltageV = vcellRaw * 0.000078125f;
    const float socPercent = socRaw / 256.0f;
    Serial.printf("[MAX17048] BATTERY: voltage=%.3f V, SOC=%.1f %%\n",
                  voltageV, socPercent);
  }

  delay(READ_INTERVAL_MS);
}
