#pragma once
#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint64_t time_us, gyro_us, orientation_us;
    float acceleration[3], gyroscope[3], quaternion[4];
    bool reliable;
} fall_sample_t;

typedef struct {
    float low_g, impact_g, rotation_rad_s, tilt_deg, quiet_rad_s;
    uint64_t max_gap_us, auxiliary_age_us, impact_window_us;
    uint64_t confirmation_us, quiet_us, cooldown_us, warmup_us;
} fall_config_t;

typedef struct {
    uint64_t detected_us, impact_us;
    float peak_g, peak_rad_s, tilt_deg;
    bool low_g_seen;
} fall_event_t;

typedef struct {
    fall_config_t config;
    uint64_t last_us, warmup_start_us, low_us, rotation_us, impact_us;
    uint64_t quiet_start_us, cooldown_until_us;
    float baseline[3], peak_g, peak_rad_s, recent_rotation_rad_s;
    bool initialized, candidate, low_g_seen;
} fall_detector_t;

fall_config_t fall_default_config(void);
void fall_detector_init(fall_detector_t *detector, const fall_config_t *config);
bool fall_detector_update(fall_detector_t *detector, const fall_sample_t *sample, fall_event_t *event);
