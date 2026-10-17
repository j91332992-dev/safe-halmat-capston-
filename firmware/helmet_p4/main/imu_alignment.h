#pragma once
#include "fall_detector.h"
#include <string.h>

typedef struct {
    uint64_t time_us;
    float values[4];
    bool reliable;
} imu_aux_report_t;

typedef struct {
    imu_aux_report_t gyro[16], orientation[4];
    unsigned gyro_next, orientation_next;
} imu_alignment_t;

static inline void imu_alignment_push(imu_alignment_t *alignment, bool orientation,
                                      uint64_t time_us, const float values[4], bool reliable)
{
    imu_aux_report_t report = {.time_us = time_us, .reliable = reliable};
    memcpy(report.values, values, sizeof(report.values));
    if (orientation) alignment->orientation[alignment->orientation_next++ % 4] = report;
    else alignment->gyro[alignment->gyro_next++ % 16] = report;
}

static inline const imu_aux_report_t *imu_alignment_before(const imu_aux_report_t *reports,
                                                          unsigned count, uint64_t time_us)
{
    const imu_aux_report_t *latest = NULL;
    for (unsigned index = 0; index < count; ++index) {
        if (reports[index].time_us && reports[index].time_us <= time_us &&
                (!latest || reports[index].time_us > latest->time_us)) latest = &reports[index];
    }
    return latest;
}

static inline fall_sample_t imu_alignment_sample(const imu_alignment_t *alignment,
                                                 uint64_t time_us, const float acceleration[3],
                                                 bool reliable)
{
    fall_sample_t sample = {.time_us = time_us};
    memcpy(sample.acceleration, acceleration, sizeof(sample.acceleration));
    const imu_aux_report_t *gyro = imu_alignment_before(alignment->gyro, 16, time_us);
    const imu_aux_report_t *orientation = imu_alignment_before(alignment->orientation, 4, time_us);
    if (gyro && orientation) {
        sample.gyro_us = gyro->time_us;
        sample.orientation_us = orientation->time_us;
        sample.reliable = reliable && gyro->reliable && orientation->reliable;
        memcpy(sample.gyroscope, gyro->values, sizeof(sample.gyroscope));
        memcpy(sample.quaternion, orientation->values, sizeof(sample.quaternion));
    }
    return sample;
}
