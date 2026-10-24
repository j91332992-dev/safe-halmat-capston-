#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "cJSON.h"
#include "bno_sh2/sh2_SensorValue.h"

// Diagnostic units: acceleration m/s^2 (including gravity), gyro rad/s,
// rotation quaternion xyzw. Event 100=impact, 101=posture, 200=reset, 201=baseline.
typedef struct {
    uint64_t sensor_us, received_us;
    float x, y, z, w;
    uint8_t kind, sequence, status;
} hanmir_imu_record_t;

void hanmir_imu_monitor_reset(void);
void hanmir_imu_monitor_feed(const sh2_SensorValue_t *value);
void hanmir_imu_monitor_status(cJSON *object);
void hanmir_imu_monitor_stack(uint32_t available);
void hanmir_imu_baseline_request(void);
bool hanmir_imu_capture_set(bool enabled, unsigned duration_s);
esp_err_t hanmir_imu_transport_start(void);
void hanmir_imu_transport_submit(const hanmir_imu_record_t *record);
void hanmir_imu_transport_status(cJSON *object);
void hanmir_imu_calibration_status(cJSON *object);
