#include <SPI.h>
#include "config.h"
#include "uwb_interface.h"

class Dw3000Adapter : public IUwbTag {
 public:
  bool begin() override {
    SPI.begin(UWB_SPI_SCK, UWB_SPI_MISO, UWB_SPI_MOSI, UWB_SPI_CS);
    Serial.println("[UWB][CONFIG] 실제 보드에 맞는 DW3000 라이브러리와 TWR ranging 호출을 이 adapter 안에 연결하세요.");
    ready = false;
    return ready;
  }
  size_t measure(UwbMeasurement *, size_t) override {
    // 앵커별 거리와 품질만 반환한다. x,y 계산은 서버가 담당한다.
    return 0;
  }
  const char *status() const override { return ready ? "ready" : "adapter_required"; }
 private:
  bool ready = false;
};

IUwbTag *createHardwareUwb() {
  static Dw3000Adapter instance;
  return &instance;
}

