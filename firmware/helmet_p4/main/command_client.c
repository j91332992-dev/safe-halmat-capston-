#include <stdio.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
#include "hanmir.h"
#include "imu_monitor.h"
#include "cJSON.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_websocket_client.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

typedef struct { bool zone_warning; int64_t expires_us; bool evacuation; unsigned evacuation_epoch; bool local_ack; char kind[32]; char id[64]; char url[192]; int frequency; int duration; int repeats; int send_timeout_ms; } command_t;
static const char *TAG = "hanmir_command";
static QueueHandle_t commands;
// Only successful zone notices are deduplicated; other voice commands retain their behavior.
static char zone_completed[16][64];
static unsigned zone_completed_index;
static atomic_uint evacuation_epoch;
static atomic_uint playing_epoch;
static atomic_bool playing_evacuation;

bool hanmir_evacuation_audio_cancelled(void)
{
    return atomic_load(&playing_evacuation) &&
           atomic_load(&playing_epoch) != atomic_load(&evacuation_epoch);
}
static esp_websocket_client_handle_t client;

static void command_event(void *arg, esp_event_base_t base, int32_t id, void *event_data)
{
    if (id != WEBSOCKET_EVENT_DATA) return;
    esp_websocket_event_data_t *event = event_data;
    if (!event->data_ptr || event->data_len < 2 || event->payload_offset != 0 ||
        event->data_len != event->payload_len || event->data_len > 1024) return;
    cJSON *root = cJSON_ParseWithLength(event->data_ptr, event->data_len);
    if (!root) return;
    command_t command = {.frequency = 1200, .duration = 110, .repeats = 3};
    cJSON *kind = cJSON_GetObjectItem(root, "command_type");
    cJSON *id_field = cJSON_GetObjectItem(root, "command_id");
    cJSON *payload = cJSON_GetObjectItem(root, "payload");
    if (cJSON_IsString(kind)) strlcpy(command.kind, kind->valuestring, sizeof(command.kind));
    if (cJSON_IsString(id_field)) strlcpy(command.id, id_field->valuestring, sizeof(command.id));
#ifdef CONFIG_HANMIR_IMU_FALL_SHADOW
    if (!strcmp(command.kind,"set_imu_capture")) {
        cJSON *enabled=cJSON_GetObjectItem(payload,"enabled");
        cJSON *duration=cJSON_GetObjectItem(payload,"duration_s");
        bool ok=cJSON_IsBool(enabled) && hanmir_imu_capture_set(cJSON_IsTrue(enabled),
            cJSON_IsNumber(duration) && duration->valueint>0 ? (unsigned)duration->valueint : 600);
        ESP_LOGI(TAG,"IMU capture command accepted=%d",ok);
        cJSON_Delete(root);return;
    }
    if (!strcmp(command.kind,"imu_set_baseline")) {
        hanmir_imu_baseline_request();
        ESP_LOGI(TAG,"IMU baseline requested; requires 1s stable samples and operator upright confirmation");
        cJSON_Delete(root);return;
    }
#endif
    if (!strcmp(command.kind, "restart_camera")) {
        ESP_LOGI(TAG, "camera-only restart accepted=%d", hanmir_camera_source_restart());
        cJSON_Delete(root);
        return;
    }
    if (!strcmp(command.kind, "set_camera_fps")) {
        cJSON *fps = cJSON_GetObjectItem(payload, "fps");
        bool ok = cJSON_IsNumber(fps) && hanmir_camera_set_target_fps(fps->valueint);
        ESP_LOGI(TAG, "camera FPS update ok=%d target=%d", ok, hanmir_camera_target_fps());
        cJSON_Delete(root);
        return;
    }
    if (!strcmp(command.kind, "stop_evacuation")) {
        // Process outside the playback FIFO, including while downloading TTS.
        atomic_fetch_add(&evacuation_epoch, 1);
        ESP_LOGI(TAG, "evacuation stop received epoch=%u", (unsigned)atomic_load(&evacuation_epoch));
        cJSON_Delete(root);
        return;
    }
    cJSON *scope = cJSON_GetObjectItem(payload, "audio_scope");
    command.evacuation = cJSON_IsString(scope) && !strcmp(scope->valuestring, "evacuation");
    command.zone_warning = cJSON_IsString(scope) && !strcmp(scope->valuestring, "zone_warning");
    if (command.zone_warning) {
        cJSON *ttl = cJSON_GetObjectItem(payload, "valid_for_ms");
        int ms = cJSON_IsNumber(ttl) ? ttl->valueint : 5000;
        if (ms < 1 || ms > 10000) ms = 5000;
        command.expires_us = esp_timer_get_time() + (int64_t)ms * 1000;
    }
    command.evacuation_epoch = atomic_load(&evacuation_epoch);
    cJSON *asset = cJSON_GetObjectItem(payload, "local_asset");
    command.local_ack = cJSON_IsString(asset) && !strcmp(asset->valuestring, "acknowledgement");
    cJSON *url = cJSON_GetObjectItem(payload, "audio_url");
    cJSON *frequency = cJSON_GetObjectItem(payload, "frequency");
    cJSON *duration = cJSON_GetObjectItem(payload, "duration");
    cJSON *repeats = cJSON_GetObjectItem(payload, "repeats");
    cJSON *timeout = cJSON_GetObjectItem(payload, "send_timeout_ms");
    if (cJSON_IsNumber(timeout)) command.send_timeout_ms = timeout->valueint;
    if (cJSON_IsString(url)) strlcpy(command.url, url->valuestring, sizeof(command.url));
    if (cJSON_IsNumber(frequency)) command.frequency = frequency->valueint;
    if (cJSON_IsNumber(duration)) command.duration = duration->valueint;
    if (cJSON_IsNumber(repeats)) command.repeats = repeats->valueint;
    if (command.kind[0] && xQueueSend(commands, &command, 0) != pdTRUE) {
        ESP_LOGE(TAG, "command queue full: %s", command.kind);
    }
    cJSON_Delete(root);
}

static void command_task(void *arg)
{
    command_t cmd;
    for (;;) {
        if (xQueueReceive(commands, &cmd, portMAX_DELAY) != pdTRUE) continue;
        if (cmd.zone_warning) {
            bool duplicate = false;
            for (unsigned i = 0; i < 16; ++i)
                if (cmd.id[0] && !strcmp(zone_completed[i], cmd.id)) duplicate = true;
            if (duplicate) {
                ESP_LOGI(TAG, "zone duplicate skipped id=%s", cmd.id);
                hanmir_report_speaker(cmd.id, true);
                continue;
            }
            if (hanmir_call_active() || esp_timer_get_time() > cmd.expires_us) {
                ESP_LOGI(TAG, "zone deferred/expired id=%s call=%d", cmd.id, hanmir_call_active());
                hanmir_report_speaker(cmd.id, false);
                continue;
            }
        }
        atomic_store(&playing_epoch, cmd.evacuation_epoch);
        atomic_store(&playing_evacuation, cmd.evacuation);
        if (hanmir_evacuation_audio_cancelled()) {
            ESP_LOGI(TAG, "discard cancelled evacuation audio");
            atomic_store(&playing_evacuation, false);
            continue;
        }
        ESP_LOGI(TAG, "execute kind=%s id=%s", cmd.kind, cmd.id);
        bool ok = false;
        if (!strcmp(cmd.kind, "play_tone")) ok = hanmir_speaker_tone(cmd.frequency, cmd.duration);
        else if (!strcmp(cmd.kind, "play_ack")) ok = hanmir_speaker_ack();
        else if (!strcmp(cmd.kind, "play_audio")) ok = cmd.local_ack ? hanmir_speaker_ack() : hanmir_speaker_play_url(cmd.url);
        else if (!strcmp(cmd.kind, "play_alert")) {
            hanmir_call_interrupt();
            ok = true;
            int n = cmd.repeats > 5 ? 5 : cmd.repeats;
            for (int i = 0; i < n && !hanmir_evacuation_audio_cancelled(); ++i) {
                ok &= hanmir_speaker_tone(1400, 220);
                vTaskDelay(pdMS_TO_TICKS(100));
            }
        } else if (!strcmp(cmd.kind, "set_camera_timeout")) {
            esp_err_t err = hanmir_camera_set_send_timeout_ms(cmd.send_timeout_ms);
            ESP_LOGI(TAG, "set_camera_timeout result=%s", esp_err_to_name(err));
            continue;
        } else if (!strcmp(cmd.kind, "request_status")) { continue; }
        else {
            ESP_LOGW(TAG, "command %s needs P4 hardware integration", cmd.kind);
        }
        if (cmd.zone_warning && ok && cmd.id[0]) {
            strlcpy(zone_completed[zone_completed_index++ % 16], cmd.id, 64);
        }
        atomic_store(&playing_evacuation, false);
        ESP_LOGI(TAG, "complete kind=%s id=%s ok=%d", cmd.kind, cmd.id, ok);
        if (cmd.id[0]) hanmir_report_speaker(cmd.id, ok);
    }
}

// Share the existing command socket; keep only the latest sensor value.
static void orientation_task(void *arg)
{
    char packet[192];
    for (;;) {
        float yaw, pitch, roll;
        if (hanmir_network_online() && esp_websocket_client_is_connected(client) &&
            hanmir_imu_orientation(&yaw, &pitch, &roll)) {
            int length = snprintf(packet, sizeof(packet),
                "{\"type\":\"orientation\",\"yaw_deg\":%.3f,\"pitch_deg\":%.3f,\"roll_deg\":%.3f}",
                yaw, pitch, roll);
            if (length > 0 && length < sizeof(packet)) {
                // Short timeout: do not build a backlog when Wi-Fi is busy.
                esp_websocket_client_send_text(client, packet, length, pdMS_TO_TICKS(30));
            }
        }
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

esp_err_t hanmir_command_start(void)
{
    commands = xQueueCreate(8, sizeof(command_t));
    if (!commands) return ESP_ERR_NO_MEM;
    if (!CONFIG_HANMIR_SERVER_HOST[0]) {
        ESP_LOGW(TAG, "Server host not configured; command channel disabled");
        return ESP_OK;
    }
    static char uri[256];
    snprintf(uri, sizeof(uri), "ws://%s:%d/ws/device/%s", CONFIG_HANMIR_SERVER_HOST,
             CONFIG_HANMIR_SERVER_PORT, CONFIG_HANMIR_DEVICE_ID);
    esp_websocket_client_config_t config = {.uri = uri, .reconnect_timeout_ms = 2000};
    client = esp_websocket_client_init(&config);
    if (!client) return ESP_ERR_NO_MEM;
    esp_websocket_register_events(client, WEBSOCKET_EVENT_DATA, command_event, NULL);
    esp_err_t err = esp_websocket_client_start(client);
    if (err != ESP_OK) return err;
    if (xTaskCreate(command_task, "helmet_command", 6144, NULL, 4, NULL) != pdPASS) return ESP_ERR_NO_MEM;
    return xTaskCreate(orientation_task, "helmet_heading", 4096, NULL, 3, NULL) == pdPASS ? ESP_OK : ESP_ERR_NO_MEM;
}
