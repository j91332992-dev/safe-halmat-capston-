#pragma once
#include <Arduino.h>

struct UwbMeasurement {
  String anchorId;
  float distanceM;
  float quality;
};

class IUwbTag {
 public:
  virtual ~IUwbTag() = default;
  virtual bool begin() = 0;
  virtual size_t measure(UwbMeasurement *output, size_t capacity) = 0;
  virtual const char *status() const = 0;
};

IUwbTag *createMockUwb();
IUwbTag *createHardwareUwb();

