#include "fall_detector.h"
#include "imu_alignment.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>

static fall_sample_t sample_at(uint64_t time_us, float acceleration_g, float rotation, float tilt_deg)
{
    float angle = tilt_deg / 57.2957795f / 2;
    return (fall_sample_t) {
        .time_us = time_us, .gyro_us = time_us, .orientation_us = time_us, .reliable = true,
        .acceleration = {0, 0, acceleration_g * 9.80665f},
        .gyroscope = {rotation, 0, 0}, .quaternion = {sinf(angle), 0, 0, cosf(angle)},
    };
}

static unsigned feed(fall_detector_t *detector, uint64_t *time_us, unsigned samples,
                     float acceleration_g, float rotation, float tilt_deg)
{
    unsigned events = 0;
    for (unsigned index = 0; index < samples; ++index) {
        *time_us += 20000;
        fall_sample_t sample = sample_at(*time_us, acceleration_g, rotation, tilt_deg);
        events += fall_detector_update(detector, &sample, NULL);
    }
    return events;
}

static void warmup(fall_detector_t *detector, uint64_t *time_us)
{
    fall_detector_init(detector, NULL);
    *time_us = 0;
    assert(feed(detector, time_us, 75, 1, 0, 0) == 0);
}

int main(void)
{
    fall_detector_t detector;
    uint64_t time_us;
    warmup(&detector, &time_us);
    assert(feed(&detector, &time_us, 500, 1, 0, 0) == 0);
    assert(feed(&detector, &time_us, 100, 1.8f, 0.8f, 25) == 0);
    assert(feed(&detector, &time_us, 100, 1, 0, 80) == 0);
    warmup(&detector, &time_us);
    assert(feed(&detector, &time_us, 1, 3, 3, 0) == 0);
    assert(feed(&detector, &time_us, 200, 1, 0, 0) == 0);
    warmup(&detector, &time_us);
    assert(feed(&detector, &time_us, 1, 3, 0, 70) == 0);
    assert(feed(&detector, &time_us, 200, 1, 0, 70) == 0);
    warmup(&detector, &time_us);
    feed(&detector, &time_us, 5, 0.3f, 3, 0);
    feed(&detector, &time_us, 1, 3, 3, 70);
    assert(feed(&detector, &time_us, 40, 1, 0, 70) == 1);
    assert(feed(&detector, &time_us, 1, 4, 4, 0) == 0);
    assert(feed(&detector, &time_us, 100, 1, 0, 0) == 0);
    warmup(&detector, &time_us);
    feed(&detector, &time_us, 1, 3, 3, 70);
    assert(feed(&detector, &time_us, 40, 1, 0, 70) == 1);
    warmup(&detector, &time_us);
    feed(&detector, &time_us, 1, 3, 3, 70);
    time_us += 500000;
    assert(feed(&detector, &time_us, 100, 1, 0, 70) == 0);
    warmup(&detector, &time_us);
    feed(&detector, &time_us, 1, 3, 3, 70);
    fall_sample_t sample = sample_at(time_us + 20000, 1, 0, 70);
    sample.gyro_us -= 300000;
    assert(!fall_detector_update(&detector, &sample, NULL));
    assert(feed(&detector, &time_us, 100, 1, 0, 70) == 0);
    warmup(&detector, &time_us);
    sample = sample_at(time_us + 20000, 3, 3, 70);
    sample.reliable = false;
    assert(!fall_detector_update(&detector, &sample, NULL));
    assert(feed(&detector, &time_us, 100, 1, 0, 70) == 0);
    sample = sample_at(time_us + 20000, NAN, 3, 70);
    assert(!fall_detector_update(&detector, &sample, NULL));
    sample = sample_at(time_us, 3, 3, 70);
    sample.quaternion[0] = 0;
    sample.quaternion[3] = 0;
    assert(!fall_detector_update(&detector, &sample, NULL));
    warmup(&detector, &time_us);
    feed(&detector, &time_us, 1, 3, 3, 70);
    assert(feed(&detector, &time_us, 200, 1, 2, 70) == 0);
    imu_alignment_t alignment = {0};
    float values[4] = {0, 0, 0, 1};
    imu_alignment_push(&alignment, true, 100000, values, true);
    imu_alignment_push(&alignment, true, 200000, values, true);
    imu_alignment_push(&alignment, false, 120000, values, true);
    imu_alignment_push(&alignment, false, 220000, values, true);
    float acceleration[3] = {0, 0, 9.80665f};
    sample = imu_alignment_sample(&alignment, 150000, acceleration, true);
    assert(sample.reliable && sample.gyro_us == 120000 && sample.orientation_us == 100000);
    sample = imu_alignment_sample(&alignment, 50000, acceleration, true);
    assert(!sample.reliable);
    warmup(&detector, &time_us);
    unsigned aligned_events = 0;
    for (unsigned index = 0; index < 100; ++index) {
        time_us += 20000;
        fall_sample_t input = sample_at(time_us, index == 10 ? 3 : 1,
                                       index == 10 ? 3 : 0, index >= 10 ? 70 : 0);
        float gyro[4] = {input.gyroscope[0], 0, 0, 0};
        imu_alignment_push(&alignment, false, time_us, gyro, true);
        if (index % 5 == 0) imu_alignment_push(&alignment, true, time_us, input.quaternion, true);
        sample = imu_alignment_sample(&alignment, time_us, input.acceleration, true);
        aligned_events += fall_detector_update(&detector, &sample, NULL);
    }
    assert(aligned_events == 1);
    puts("Fall detector checks passed");
    return 0;
}
