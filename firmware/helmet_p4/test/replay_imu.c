#include "fall_detector.h"
#include "imu_alignment.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    FILE *input = fopen(argv[1], "r");
    if (!input) return 2;
    fall_detector_t detector;
    fall_detector_init(&detector, NULL);
    imu_alignment_t alignment = {0};
    char line[512];
    unsigned count = 0;
    uint64_t previous_received_us = 0;
    while (fgets(line, sizeof(line), input)) {
        uint64_t received_us, sensor_us;
        uint32_t raw_us;
        unsigned sensor_id, sequence, status;
        float values[4];
        int fields = sscanf(line, "%" SCNu64 ",%" SCNu64 ",%u,%u,%u,%f,%f,%f,%f,%" SCNu32,
                            &received_us, &sensor_us, &sensor_id, &sequence, &status,
                            &values[0], &values[1], &values[2], &values[3], &raw_us);
        if (fields != 10) continue;
        if (previous_received_us && received_us < previous_received_us) {
            fall_detector_init(&detector, NULL);
            memset(&alignment, 0, sizeof(alignment));
        }
        previous_received_us = received_us;
        if (sensor_id == 2) {
            imu_alignment_push(&alignment, false, sensor_us, values, status > 0);
        } else if (sensor_id == 5) {
            imu_alignment_push(&alignment, true, sensor_us, values, status > 0);
        } else if (sensor_id == 1) {
            fall_sample_t sample = imu_alignment_sample(&alignment, sensor_us, values, status > 0);
            fall_event_t event;
            if (fall_detector_update(&detector, &sample, &event)) {
                printf("FALL_SUSPECTED,%u,%" PRIu64 ",%.3f,%.3f,%.1f\n",
                       ++count, event.detected_us, event.peak_g, event.peak_rad_s, event.tilt_deg);
            }
        }
    }
    fclose(input);
    return 0;
}
