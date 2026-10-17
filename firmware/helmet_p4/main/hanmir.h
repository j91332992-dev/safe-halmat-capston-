#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
#include "fall_detector.h"

esp_err_t hanmir_network_start(void);
esp_err_t hanmir_pin_guard_validate(void);
bool hanmir_network_online(void);
int hanmir_network_rssi(void);
void hanmir_api_task(void *arg);
bool hanmir_audio_upload_wav(const uint8_t *wav, size_t length);
esp_err_t hanmir_camera_transport_start(void);
bool hanmir_camera_submit_jpeg(const uint8_t *jpeg, size_t length, uint16_t width, uint16_t height);
bool hanmir_camera_connected(void);
uint32_t hanmir_camera_dropped(void);
int hanmir_camera_send_timeout_ms(void);
esp_err_t hanmir_camera_set_send_timeout_ms(int value);
esp_err_t hanmir_camera_source_start(void);
bool hanmir_camera_source_ready(void);
esp_err_t hanmir_voice_start(void);
bool hanmir_voice_ready(void);
bool hanmir_voice_ns_ready(void);
void hanmir_voice_set_playback(bool playing);
esp_err_t hanmir_speaker_start(void);
bool hanmir_speaker_ready(void);
bool hanmir_speaker_tone(int frequency, int duration_ms);
bool hanmir_speaker_play_url(const char *path);
bool hanmir_speaker_call_begin(void);
bool hanmir_speaker_call_write(const uint8_t *pcm, size_t bytes);
void hanmir_speaker_call_end(void);
esp_err_t hanmir_call_start(void);
bool hanmir_call_active(void);
void hanmir_call_interrupt(void);
void hanmir_call_feed(const int16_t *pcm, size_t samples);
esp_err_t hanmir_command_start(void);
bool hanmir_report_speaker(const char *command_id, bool ok);
void hanmir_sensors_init(void);
bool hanmir_battery_percent(float *percent);
bool hanmir_imu_ready(void);
bool hanmir_imu_orientation(float *yaw, float *pitch, float *roll);
bool hanmir_imu_last_fall(fall_event_t *event, uint32_t *count);
esp_err_t hanmir_fall_start(void);
void hanmir_fall_detected(const fall_event_t *event);
bool hanmir_fall_response_context(char *incident, size_t capacity);
bool hanmir_fall_busy(void);
int hanmir_fall_remaining_ms(void);
void hanmir_fall_voice_started(const char *incident_id);
bool hanmir_fall_upload_wav(const uint8_t *wav, size_t length, const char *incident_id);

bool hanmir_speaker_ack(void);
