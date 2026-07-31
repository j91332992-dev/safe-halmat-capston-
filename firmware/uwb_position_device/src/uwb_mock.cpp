#include <math.h>
#include "uwb_interface.h"

class MockUwbTag : public IUwbTag {
 public:
  bool begin() override { return true; }
  size_t measure(UwbMeasurement *out, size_t capacity) override {
    if (capacity < 4) return 0;
    float t = millis() / 1000.0f;
    float x = 6.0f + sinf(t / 5.0f) * 4.0f;
    float y = 4.0f + cosf(t / 6.0f) * 2.5f;
    const float ax[4] = {0, 12, 12, 0};
    const float ay[4] = {0, 0, 8, 8};
    for (int i = 0; i < 4; ++i) {
      out[i].anchorId = "anchor-00" + String(i + 1);
      out[i].distanceM = hypotf(x - ax[i], y - ay[i]);
      out[i].quality = 0.95f;
    }
    return 4;
  }
  const char *status() const override { return "mock_ready"; }
};

IUwbTag *createMockUwb() {
  static MockUwbTag instance;
  return &instance;
}

