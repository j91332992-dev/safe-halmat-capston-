#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"

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
esp_err_t hanmir_camera_source_start(void);
esp_err_t hanmir_voice_start(void);
void hanmir_voice_set_playback(bool playing);
esp_err_t hanmir_speaker_start(void);
bool hanmir_speaker_ready(void);
bool hanmir_speaker_tone(int frequency, int duration_ms);
bool hanmir_speaker_play_url(const char *path);
esp_err_t hanmir_command_start(void);
bool hanmir_report_speaker(const char *command_id, bool ok);
void hanmir_sensors_init(void);
bool hanmir_battery_percent(float *percent);
bool hanmir_imu_ready(void);
