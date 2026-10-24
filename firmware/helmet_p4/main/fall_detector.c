#include "fall_detector.h"
#include <math.h>
#include <string.h>

fall_config_t fall_default_config(void)
{
    return (fall_config_t) {
        .low_g = 0.5f, .impact_g = 2.5f, .rotation_rad_s = 2.0f,
        .tilt_deg = 45.0f, .quiet_rad_s = 0.6f,
        .max_gap_us = 100000, .auxiliary_age_us = 200000,
        .impact_window_us = 3000000, .confirmation_us = 200000,
        .quiet_us = 600000, .cooldown_us = 10000000, .warmup_us = 1000000,
    };
}

void fall_detector_init(fall_detector_t *detector, const fall_config_t *config)
{
    memset(detector, 0, sizeof(*detector));
    detector->config = config ? *config : fall_default_config();
}

static float magnitude(const float vector[3])
{
    return sqrtf(vector[0] * vector[0] + vector[1] * vector[1] + vector[2] * vector[2]);
}

static bool recent(uint64_t now, uint64_t then, uint64_t window)
{
    return then > 0 && now >= then && now - then <= window;
}

bool fall_detector_update(fall_detector_t *detector, const fall_sample_t *sample, fall_event_t *event)
{
    const fall_config_t config = detector->config;
    bool valid = sample->reliable && sample->time_us > 0;
    for (unsigned axis = 0; axis < 3; ++axis) {
        valid = valid && isfinite(sample->acceleration[axis]) && isfinite(sample->gyroscope[axis]);
    }
    float quaternion_norm = 0;
    for (unsigned component = 0; component < 4; ++component) {
        valid = valid && isfinite(sample->quaternion[component]);
        quaternion_norm += sample->quaternion[component] * sample->quaternion[component];
    }
    valid = valid && quaternion_norm > 0.8f && quaternion_norm < 1.2f &&
        recent(sample->time_us, sample->gyro_us, config.auxiliary_age_us) &&
        recent(sample->time_us, sample->orientation_us, config.auxiliary_age_us);
    if (!valid || (detector->last_us && (sample->time_us <= detector->last_us ||
            sample->time_us - detector->last_us > config.max_gap_us))) {
        uint64_t cooldown = detector->cooldown_until_us;
        fall_detector_init(detector, &config);
        detector->cooldown_until_us = cooldown;
        return false;
    }
    float quaternion_x = sample->quaternion[0], quaternion_y = sample->quaternion[1];
    float quaternion_z = sample->quaternion[2], quaternion_w = sample->quaternion[3];
    float gravity[3] = {
        2 * (quaternion_x * quaternion_z - quaternion_w * quaternion_y) / quaternion_norm,
        2 * (quaternion_y * quaternion_z + quaternion_w * quaternion_x) / quaternion_norm,
        1 - 2 * (quaternion_x * quaternion_x + quaternion_y * quaternion_y) / quaternion_norm,
    };
    uint64_t elapsed_us = detector->last_us ? sample->time_us - detector->last_us : 0;
    detector->last_us = sample->time_us;
    float acceleration_g = magnitude(sample->acceleration) / 9.80665f;
    float rotation = magnitude(sample->gyroscope);
    if (!detector->initialized) {
        memcpy(detector->baseline, gravity, sizeof(gravity));
        detector->warmup_start_us = sample->time_us;
        detector->initialized = true;
    }
    if (sample->time_us < detector->cooldown_until_us) return false;
    if (rotation >= config.rotation_rad_s) {
        detector->rotation_us = sample->time_us;
        detector->recent_rotation_rad_s = rotation;
    }
    if (acceleration_g < config.low_g) detector->low_us = sample->time_us;
    if (!detector->candidate && sample->time_us - detector->warmup_start_us >= config.warmup_us &&
            acceleration_g >= config.impact_g) {
        detector->candidate = true;
        detector->impact_us = sample->time_us;
        detector->peak_g = acceleration_g;
        detector->peak_rad_s = recent(sample->time_us, detector->rotation_us, 500000) ? detector->recent_rotation_rad_s : rotation;
        detector->low_g_seen = recent(sample->time_us, detector->low_us, 1000000);
    }
    if (detector->candidate) {
        detector->peak_g = fmaxf(detector->peak_g, acceleration_g);
        detector->peak_rad_s = fmaxf(detector->peak_rad_s, rotation);
        float baseline_norm = magnitude(detector->baseline);
        float cosine = 0;
        for (unsigned axis = 0; axis < 3; ++axis) cosine += detector->baseline[axis] * gravity[axis];
        float tilt = acosf(fmaxf(-1, fminf(1, cosine / baseline_norm))) * 57.2957795f;
        bool quiet = rotation <= config.quiet_rad_s && fabsf(acceleration_g - 1) <= 0.2f &&
            tilt >= config.tilt_deg;
        if (!quiet) detector->quiet_start_us = 0;
        else if (!detector->quiet_start_us) detector->quiet_start_us = sample->time_us;
        if (sample->time_us - detector->impact_us > config.impact_window_us) {
            detector->candidate = false;
            detector->quiet_start_us = 0;
        } else if (detector->peak_rad_s >= config.rotation_rad_s && detector->quiet_start_us &&
                sample->time_us - detector->impact_us >= config.confirmation_us &&
                sample->time_us - detector->quiet_start_us >= config.quiet_us) {
            if (event) *event = (fall_event_t) {
                .detected_us = sample->time_us, .impact_us = detector->impact_us,
                .peak_g = detector->peak_g, .peak_rad_s = detector->peak_rad_s,
                .tilt_deg = tilt, .low_g_seen = detector->low_g_seen,
            };
            detector->candidate = false;
            detector->quiet_start_us = 0;
            detector->cooldown_until_us = sample->time_us + config.cooldown_us;
            memcpy(detector->baseline, gravity, sizeof(gravity));
            return true;
        }
    } else if (acceleration_g >= 0.8f && acceleration_g <= 1.2f && rotation < config.quiet_rad_s) {
        float weight = 1 - expf(-(float)elapsed_us / 2000000.0f);
        for (unsigned axis = 0; axis < 3; ++axis) {
            detector->baseline[axis] += weight * (gravity[axis] - detector->baseline[axis]);
        }
    }
    return false;
}
