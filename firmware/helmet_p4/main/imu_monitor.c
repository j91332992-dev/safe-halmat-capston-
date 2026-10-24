#include "imu_monitor.h"
#include "hanmir.h"
#include "imu_alignment.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include <math.h>
#include <stdatomic.h>
#include <string.h>

static const char *TAG = "hanmir_imu";
static imu_alignment_t alignment;
static fall_detector_t impact_detector;
static atomic_bool calibration_requested;
static portMUX_TYPE status_mux = portMUX_INITIALIZER_UNLOCKED;
static struct {
    uint32_t count[4], sequence_missing[4], duplicate[4], resets, invalid, unaligned;
    uint32_t impact_events, posture_events, baseline_generation, gaps;
    uint64_t last_rx[4], max_rx_gap[4];
    uint64_t last_sensor[4], max_sensor_gap[4];
    uint32_t nonmonotonic[4], unreliable[4];
    uint8_t accuracy[4];
    float acceleration_g, gyro_rad_s, relative_tilt;
    bool baseline_ready;
} status;
static uint8_t last_sequence[4];
static bool sequence_seen[4];
static float baseline[3];
static uint64_t previous_sample_us, tilt_since_us, quiet_since_us, posture_cooldown_us;
static bool tilt_latched;
static atomic_ullong resource_refresh_us;
static atomic_uint heap_free, heap_min, heap_largest, psram_free, psram_min;
static atomic_uint sensor_stack_min;

void hanmir_imu_monitor_stack(uint32_t available)
{
    uint32_t old=atomic_load(&sensor_stack_min);
    if (!old || available<old) atomic_store(&sensor_stack_min,available);
}

static void clear_posture_evidence(void)
{
    previous_sample_us = tilt_since_us = quiet_since_us = 0;
}

void hanmir_imu_monitor_reset(void)
{
    memset(&alignment, 0, sizeof(alignment));
    fall_detector_init(&impact_detector, NULL);
    memset(sequence_seen, 0, sizeof(sequence_seen));
    clear_posture_evidence();
    tilt_latched = false;
    portENTER_CRITICAL(&status_mux);
    status.resets++;
    status.baseline_ready = false;
    memset(status.last_rx, 0, sizeof(status.last_rx));
    memset(status.last_sensor, 0, sizeof(status.last_sensor));
    portEXIT_CRITICAL(&status_mux);
    atomic_store(&calibration_requested, false);
    hanmir_imu_record_t record = {.kind=200, .received_us=esp_timer_get_time()};
    hanmir_imu_transport_submit(&record);
}

void hanmir_imu_baseline_request(void)
{
    atomic_store(&calibration_requested, true);
}

static bool sample_valid(const fall_sample_t *sample, float *g, float *rotation, float gravity[3])
{
    if (!sample->reliable || !sample->time_us || sample->gyro_us>sample->time_us ||
        sample->orientation_us>sample->time_us || sample->time_us-sample->gyro_us>200000 ||
        sample->time_us-sample->orientation_us>200000) return false;
    float acc=0, gyro=0, norm=0;
    for (int i=0; i<3; i++) {
        if (!isfinite(sample->acceleration[i]) || !isfinite(sample->gyroscope[i])) return false;
        acc+=sample->acceleration[i]*sample->acceleration[i];
        gyro+=sample->gyroscope[i]*sample->gyroscope[i];
    }
    for (int i=0; i<4; i++) {
        if (!isfinite(sample->quaternion[i])) return false;
        norm+=sample->quaternion[i]*sample->quaternion[i];
    }
    if (norm<0.8f || norm>1.2f) return false;
    float x=sample->quaternion[0], y=sample->quaternion[1], z=sample->quaternion[2], w=sample->quaternion[3];
    gravity[0]=2*(x*z-w*y)/norm;
    gravity[1]=2*(y*z+w*x)/norm;
    gravity[2]=1-2*(x*x+y*y)/norm;
    *g=sqrtf(acc)/9.80665f; *rotation=sqrtf(gyro);
    return true;
}

static void evaluate_posture(const fall_sample_t *sample)
{
    float g, rotation, gravity[3];
    bool valid=sample_valid(sample,&g,&rotation,gravity);
    if (!valid || (previous_sample_us && (sample->time_us<=previous_sample_us ||
        sample->time_us-previous_sample_us>100000))) {
        clear_posture_evidence();
        portENTER_CRITICAL(&status_mux);
        status.unaligned++;
        portEXIT_CRITICAL(&status_mux);
        return;
    }
    previous_sample_us=sample->time_us;
    bool quiet=rotation<=0.6f && g>=0.8f && g<=1.2f;
    if (!quiet) quiet_since_us=0;
    else if (!quiet_since_us) quiet_since_us=sample->time_us;
    if (atomic_load(&calibration_requested)) {
        if (quiet_since_us && sample->time_us-quiet_since_us>=1000000) {
            memcpy(baseline,gravity,sizeof(baseline));
            portENTER_CRITICAL(&status_mux);
            status.baseline_ready=true;
            status.baseline_generation++;
            portEXIT_CRITICAL(&status_mux);
            atomic_store(&calibration_requested,false);
            tilt_since_us=0; tilt_latched=false;
            hanmir_imu_record_t record={.kind=201,.sensor_us=sample->time_us,
                .received_us=esp_timer_get_time(),.status=1,
                .x=baseline[0],.y=baseline[1],.z=baseline[2]};
            hanmir_imu_transport_submit(&record);
            ESP_LOGI(TAG,"shadow baseline saved after 1s stable input; operator must confirm upright pose");
        }
        else {tilt_since_us=0;return;}
        // Calibration never assumes a stationary sensor is necessarily upright.
    }
    portENTER_CRITICAL(&status_mux);
    bool ready=status.baseline_ready;
    status.acceleration_g=g; status.gyro_rad_s=rotation;
    portEXIT_CRITICAL(&status_mux);
    if (!ready) return;
    float dot=0;
    for (int i=0;i<3;i++) dot+=baseline[i]*gravity[i];
    float tilt=acosf(fminf(1,fmaxf(-1,dot)))*57.2957795f;
    portENTER_CRITICAL(&status_mux);
    status.relative_tilt=tilt;
    portEXIT_CRITICAL(&status_mux);
    if (tilt<40) {tilt_latched=false; tilt_since_us=0;}
    else if (tilt<CONFIG_HANMIR_POSTURE_TILT_DEG) tilt_since_us=0;
    else if (!tilt_since_us) tilt_since_us=sample->time_us;
    if (!tilt_latched && tilt_since_us && quiet_since_us &&
        sample->time_us-tilt_since_us>=CONFIG_HANMIR_POSTURE_HOLD_MS*1000ULL &&
        sample->time_us-quiet_since_us>=1000000 && sample->time_us>=posture_cooldown_us) {
        tilt_latched=true; posture_cooldown_us=sample->time_us+10000000;
        portENTER_CRITICAL(&status_mux);
        status.posture_events++;
        portEXIT_CRITICAL(&status_mux);
        hanmir_imu_record_t record={.kind=101,.status=1,.sensor_us=sample->time_us,
            .received_us=esp_timer_get_time(),.x=g,.y=rotation,.z=tilt,
            .w=hanmir_call_active()?1:0};
        hanmir_imu_transport_submit(&record);
        ESP_LOGW(TAG,"SHADOW posture candidate g=%.3f gyro=%.3f tilt=%.1f; no automatic alarm",g,rotation,tilt);
    }
}

void hanmir_imu_monitor_feed(const sh2_SensorValue_t *value)
{
    int index=value->sensorId==SH2_ACCELEROMETER?0:
        value->sensorId==SH2_GYROSCOPE_CALIBRATED?1:value->sensorId==SH2_ROTATION_VECTOR?2:
        value->sensorId==SH2_GAME_ROTATION_VECTOR?3:-1;
    if (index<0) return;
    uint64_t now=esp_timer_get_time();
    hanmir_imu_record_t record={.kind=value->sensorId,.sequence=value->sequence,
        .status=value->status,.sensor_us=value->timestamp,.received_us=now};
    if (index==0) {record.x=value->un.accelerometer.x;record.y=value->un.accelerometer.y;record.z=value->un.accelerometer.z;}
    else if (index==1) {record.x=value->un.gyroscope.x;record.y=value->un.gyroscope.y;record.z=value->un.gyroscope.z;}
    else if (index==3) {record.x=value->un.gameRotationVector.i;record.y=value->un.gameRotationVector.j;
          record.z=value->un.gameRotationVector.k;record.w=value->un.gameRotationVector.real;}
    else {record.x=value->un.rotationVector.i;record.y=value->un.rotationVector.j;
          record.z=value->un.rotationVector.k;record.w=value->un.rotationVector.real;}
    if (!isfinite(record.x)||!isfinite(record.y)||!isfinite(record.z)||!isfinite(record.w)) {
        portENTER_CRITICAL(&status_mux);status.invalid++;portEXIT_CRITICAL(&status_mux);return;
    }
    portENTER_CRITICAL(&status_mux);
    status.count[index]++;
    status.accuracy[index]=value->status;
    if (status.last_rx[index]) {
        uint64_t gap=now-status.last_rx[index];
        if (gap>status.max_rx_gap[index]) status.max_rx_gap[index]=gap;
        if (gap>(index>=2?200000:100000)) status.gaps++;
    }
    status.last_rx[index]=now;
    if (status.last_sensor[index]) {
        if (value->timestamp<=status.last_sensor[index]) status.nonmonotonic[index]++;
        else if (value->timestamp-status.last_sensor[index]>status.max_sensor_gap[index])
            status.max_sensor_gap[index]=value->timestamp-status.last_sensor[index];
    }
    status.last_sensor[index]=value->timestamp;
    if (!value->status) status.unreliable[index]++;
    if (sequence_seen[index]) {
        uint8_t delta=(uint8_t)(value->sequence-last_sequence[index]);
        if (!delta) status.duplicate[index]++;
        else if (delta<128) status.sequence_missing[index]+=delta-1;
        // Larger jumps are counted as discontinuities, not fabricated missing counts.
        else status.gaps++;
    }
    last_sequence[index]=value->sequence;sequence_seen[index]=true;
    portEXIT_CRITICAL(&status_mux);
    hanmir_imu_transport_submit(&record);
    float values[4]={record.x,record.y,record.z,record.w};
    if (index==1 || index==3) imu_alignment_push(&alignment,index==3,value->timestamp,values,value->status>0);
    else if (index==0) {
        fall_sample_t sample=imu_alignment_sample(&alignment,value->timestamp,values,value->status>0);
        fall_event_t event;
        if (fall_detector_update(&impact_detector,&sample,&event)) {
            portENTER_CRITICAL(&status_mux);status.impact_events++;portEXIT_CRITICAL(&status_mux);
            hanmir_imu_record_t candidate={.kind=100,.status=1,.sensor_us=event.detected_us,
                .received_us=now,.x=event.peak_g,.y=event.peak_rad_s,.z=event.tilt_deg,
                .w=(hanmir_call_active()?1:0)|(event.low_g_seen?2:0)};
            hanmir_imu_transport_submit(&candidate);
            ESP_LOGW(TAG,"SHADOW impact candidate peak_g=%.3f gyro=%.3f tilt=%.1f; no automatic alarm",event.peak_g,event.peak_rad_s,event.tilt_deg);
        }
        evaluate_posture(&sample);
    }
}

void hanmir_imu_monitor_status(cJSON *object)
{
    portENTER_CRITICAL(&status_mux);
    __typeof__(status) snapshot=status;
    portEXIT_CRITICAL(&status_mux);
    static const char *names[]={"accel","gyro","rotation","fall_rotation"};
    uint64_t now=esp_timer_get_time();
    for (int i=0;i<4;i++) {
        cJSON *item=cJSON_AddObjectToObject(object,names[i]);
        cJSON_AddNumberToObject(item,"received",snapshot.count[i]);
        cJSON_AddNumberToObject(item,"sequence_missing",snapshot.sequence_missing[i]);
        cJSON_AddNumberToObject(item,"duplicates",snapshot.duplicate[i]);
        cJSON_AddNumberToObject(item,"age_ms",snapshot.last_rx[i]?(now-snapshot.last_rx[i])/1000.0:-1);
        cJSON_AddNumberToObject(item,"max_callback_gap_ms",snapshot.max_rx_gap[i]/1000.0);
        cJSON_AddNumberToObject(item,"max_sensor_gap_ms",snapshot.max_sensor_gap[i]/1000.0);
        cJSON_AddNumberToObject(item,"nonmonotonic_sensor_time",snapshot.nonmonotonic[i]);
        cJSON_AddNumberToObject(item,"unreliable",snapshot.unreliable[i]);
        cJSON_AddNumberToObject(item,"accuracy",snapshot.accuracy[i]);
    }
    cJSON_AddStringToObject(object,"fall_mode","shadow");
    cJSON_AddBoolToObject(object,"baseline_ready",snapshot.baseline_ready);
    cJSON_AddNumberToObject(object,"baseline_generation",snapshot.baseline_generation);
    cJSON_AddBoolToObject(object,"calibration_pending",atomic_load(&calibration_requested));
    cJSON_AddNumberToObject(object,"relative_tilt_deg",snapshot.relative_tilt);
    cJSON_AddNumberToObject(object,"acceleration_g",snapshot.acceleration_g);
    cJSON_AddNumberToObject(object,"gyro_rad_s",snapshot.gyro_rad_s);
    cJSON_AddNumberToObject(object,"impact_candidates",snapshot.impact_events);
    cJSON_AddNumberToObject(object,"posture_candidates",snapshot.posture_events);
    cJSON_AddNumberToObject(object,"sensor_resets",snapshot.resets);
    cJSON_AddNumberToObject(object,"invalid_values",snapshot.invalid);
    cJSON_AddNumberToObject(object,"unaligned_or_discontinuous",snapshot.unaligned);
    cJSON_AddNumberToObject(object,"long_gaps",snapshot.gaps);
    uint64_t refresh=atomic_load(&resource_refresh_us);
    if (now>=refresh && atomic_compare_exchange_strong(&resource_refresh_us,&refresh,now+5000000)) {
        atomic_store(&heap_free,heap_caps_get_free_size(MALLOC_CAP_INTERNAL));
        atomic_store(&heap_min,heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL));
        atomic_store(&heap_largest,heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL));
        atomic_store(&psram_free,heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
        atomic_store(&psram_min,heap_caps_get_minimum_free_size(MALLOC_CAP_SPIRAM));
    }
    cJSON_AddNumberToObject(object,"heap_free",atomic_load(&heap_free));
    cJSON_AddNumberToObject(object,"heap_min",atomic_load(&heap_min));
    cJSON_AddNumberToObject(object,"heap_largest",atomic_load(&heap_largest));
    cJSON_AddNumberToObject(object,"psram_free",atomic_load(&psram_free));
    cJSON_AddNumberToObject(object,"psram_min",atomic_load(&psram_min));
    cJSON_AddBoolToObject(object,"call_active",hanmir_call_active());
    cJSON_AddNumberToObject(object,"camera_dropped",hanmir_camera_dropped());
    cJSON_AddNumberToObject(object,"camera_encode_skipped",hanmir_camera_encode_skipped());
    cJSON_AddNumberToObject(object,"rssi",hanmir_network_rssi());
    cJSON_AddNumberToObject(object,"sensor_stack_min",atomic_load(&sensor_stack_min));
    hanmir_imu_transport_status(object);
    hanmir_imu_calibration_status(object);
}
