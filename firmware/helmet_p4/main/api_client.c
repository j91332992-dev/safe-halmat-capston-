#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdatomic.h>
#include "hanmir.h"
#include "imu_monitor.h"
#include "cJSON.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "miniz.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "hanmir_api";
static atomic_bool audio_zlib_supported;
static tdefl_compressor *audio_compressor;
static atomic_uint audio_raw_bytes, audio_wire_bytes, audio_compressed_clips;

static esp_err_t capability_header(esp_http_client_event_t *event)
{
    if (event->event_id == HTTP_EVENT_ON_HEADER && event->header_key && event->header_value &&
        !strcasecmp(event->header_key, "X-Hanmir-Audio-Transport") &&
        !strcmp(event->header_value, "wav-zlib-v1")) *(bool *)event->user_data = true;
    return ESP_OK;
}

static void make_url(char *out, size_t size, const char *path)
{
    snprintf(out, size, "http://%s:%d%s", CONFIG_HANMIR_SERVER_HOST,
             CONFIG_HANMIR_SERVER_PORT, path);
}

static bool write_all(esp_http_client_handle_t client, const void *data, size_t length)
{
    const char *cursor = data;
    while (length) {
        int written = esp_http_client_write(client, cursor, length);
        if (written <= 0) return false;
        cursor += written;
        length -= written;
    }
    return true;
}

static bool post_json(const char *path, cJSON *body)
{
    char url[256];
    make_url(url, sizeof(url), path);
    char *payload = cJSON_PrintUnformatted(body);
    if (!payload) return false;
    bool audio_capability = false;
    esp_http_client_config_t config = {.url = url, .timeout_ms = 2500,
        .event_handler = capability_header, .user_data = &audio_capability};
    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (!client) {
        cJSON_free(payload);
        return false;
    }
    esp_http_client_set_method(client, HTTP_METHOD_POST);
    esp_http_client_set_header(client, "Content-Type", "application/json");
    esp_http_client_set_post_field(client, payload, strlen(payload));
    esp_err_t err = esp_http_client_perform(client);
    int status = err == ESP_OK ? esp_http_client_get_status_code(client) : 0;
    if (!strcmp(path, "/api/devices/heartbeat") && status >= 200 && status < 300)
        atomic_store(&audio_zlib_supported, audio_capability);
    if (err != ESP_OK || status < 200 || status >= 300) {
        ESP_LOGW(TAG, "POST %s failed err=%s status=%d", path, esp_err_to_name(err), status);
    }
    esp_http_client_cleanup(client);
    cJSON_free(payload);
    return status >= 200 && status < 300;
}

static cJSON *common_body(void)
{
    cJSON *body = cJSON_CreateObject();
    cJSON_AddStringToObject(body, "organization_id", CONFIG_HANMIR_ORGANIZATION_ID);
    cJSON_AddStringToObject(body, "site_id", CONFIG_HANMIR_SITE_ID);
    cJSON_AddStringToObject(body, "device_id", CONFIG_HANMIR_DEVICE_ID);
    cJSON_AddStringToObject(body, "worker_id", CONFIG_HANMIR_WORKER_ID);
    cJSON_AddStringToObject(body, "helmet_id", CONFIG_HANMIR_HELMET_ID);
    return body;
}

void hanmir_api_task(void *arg)
{
    bool registered = false;
    while (true) {
        if (!hanmir_network_online() || !CONFIG_HANMIR_SERVER_HOST[0]) {
            registered = false;
            vTaskDelay(pdMS_TO_TICKS(1000));
            continue;
        }
        cJSON *body = common_body();
        if (!registered) {
            cJSON_AddStringToObject(body, "device_type", "assistant_device");
            cJSON_AddStringToObject(body, "firmware_version", "2.0.0-p4-cal2-call1-zone1-camretry1-20261025");
            registered = post_json("/api/devices/register", body);
            cJSON_Delete(body);
            vTaskDelay(pdMS_TO_TICKS(registered ? 100 : 5000));
            continue;
        }
        cJSON_AddNumberToObject(body, "rssi", hanmir_network_rssi());
        float battery = 0;
        bool battery_ready = hanmir_battery_percent(&battery);
        if (battery_ready) cJSON_AddNumberToObject(body, "battery", battery);
        cJSON *components = cJSON_AddObjectToObject(body, "component_status");
        cJSON_AddStringToObject(components, "network", "ready");
        cJSON_AddStringToObject(components, "camera", hanmir_camera_source_ready() ? "capturing" : "unavailable");
        hanmir_camera_source_diagnostics(cJSON_AddObjectToObject(components, "camera_diagnostics"));
        cJSON_AddStringToObject(components, "battery", battery_ready ? "ready" : "unavailable");
        cJSON_AddStringToObject(components, "imu", hanmir_imu_ready() ? "ready" : "unverified");
#ifdef CONFIG_HANMIR_IMU_FALL_SHADOW
        hanmir_imu_monitor_status(cJSON_AddObjectToObject(components,"imu_diagnostics"));
#endif
        float imu_yaw = 0, imu_pitch = 0, imu_roll = 0;
        if (hanmir_imu_orientation(&imu_yaw, &imu_pitch, &imu_roll)) {
            cJSON_AddNumberToObject(components, "imu_yaw_deg", imu_yaw);
            cJSON_AddNumberToObject(components, "imu_pitch_deg", imu_pitch);
            cJSON_AddNumberToObject(components, "imu_roll_deg", imu_roll);
        }
        cJSON_AddStringToObject(components, "speaker", hanmir_speaker_ready() ? "initialized" : "unavailable");
        hanmir_call_diagnostics(cJSON_AddObjectToObject(components,"call_diagnostics"));
        cJSON_AddStringToObject(components, "video_transport", hanmir_camera_connected() ? "connected" : "disconnected");
#if CONFIG_HANMIR_ENABLE_VOICE
        cJSON_AddStringToObject(components, "mic", hanmir_voice_ready() ? "initialized" : "unavailable");
        cJSON_AddStringToObject(components, "noise_suppression", hanmir_voice_ns_ready() ? "ready" : "unavailable");
#else
        cJSON_AddStringToObject(components, "mic", "disabled");
#endif
        cJSON_AddNumberToObject(components, "camera_dropped", hanmir_camera_dropped());
        cJSON_AddNumberToObject(components, "camera_send_timeout_ms", hanmir_camera_send_timeout_ms());
        cJSON_AddNumberToObject(components, "camera_ws_buffer_bytes", CONFIG_HANMIR_CAMERA_WS_BUFFER_BYTES);
        cJSON_AddNumberToObject(components, "camera_target_fps", hanmir_camera_target_fps());
        cJSON_AddNumberToObject(components, "camera_encode_skipped", hanmir_camera_encode_skipped());
        cJSON_AddBoolToObject(components, "audio_lossless_transport", atomic_load(&audio_zlib_supported));
        cJSON_AddNumberToObject(components, "audio_raw_bytes", atomic_load(&audio_raw_bytes));
        cJSON_AddNumberToObject(components, "audio_wire_bytes", atomic_load(&audio_wire_bytes));
        cJSON_AddNumberToObject(components, "audio_compressed_clips", atomic_load(&audio_compressed_clips));
        if (!post_json("/api/devices/heartbeat", body)) registered = false;
        cJSON_Delete(body);
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

bool hanmir_audio_upload_wav(const uint8_t *wav, size_t length)
{
    if (!hanmir_network_online() || !wav || length < 44) return false;
    const uint8_t *wire = wav;
    size_t wire_length = length;
    uint8_t *compressed = NULL;
    if (atomic_load(&audio_zlib_supported)) {
        int64_t began = esp_timer_get_time();
        if (!audio_compressor) audio_compressor = heap_caps_malloc(sizeof(tdefl_compressor), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
        compressed = heap_caps_malloc(length + 64, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
        if (audio_compressor && compressed && tdefl_init(audio_compressor, NULL, NULL, TDEFL_WRITE_ZLIB_HEADER | 1) == TDEFL_STATUS_OKAY) {
            size_t consumed = length, produced = length + 64;
            tdefl_status result = tdefl_compress(audio_compressor, wav, &consumed, compressed, &produced, TDEFL_FINISH);
            if (result == TDEFL_STATUS_DONE && consumed == length && produced < length * 95 / 100) {
                wire = compressed; wire_length = produced;
                atomic_fetch_add(&audio_compressed_clips, 1);
            }
        }
        ESP_LOGI(TAG, "audio transport raw=%u wire=%u compression_us=%lld lossless=%d",
                 (unsigned)length, (unsigned)wire_length, (long long)(esp_timer_get_time()-began), wire != wav);
    }
    char url[256], head[512];
    make_url(url, sizeof(url), "/api/audio/upload");
    const char *boundary = "hanmirp4voice";
    int head_len = snprintf(head, sizeof(head),
        "--%s\r\nContent-Disposition: form-data; name=\"device_id\"\r\n\r\n%s\r\n"
        "--%s\r\nContent-Disposition: form-data; name=\"worker_id\"\r\n\r\n%s\r\n"
        "--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"speech.wav\"\r\n"
        "Content-Type: %s\r\n\r\n",
        boundary, CONFIG_HANMIR_DEVICE_ID, boundary, CONFIG_HANMIR_WORKER_ID, boundary,
        wire != wav ? "application/x-hanmir-wav-zlib" : "audio/wav");
    const char *tail = "\r\n--hanmirp4voice--\r\n";
    if (head_len <= 0 || head_len >= sizeof(head)) { free(compressed); return false; }
    esp_http_client_config_t config = {.url = url, .timeout_ms = 12000};
    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (!client) { free(compressed); return false; }
    esp_http_client_set_method(client, HTTP_METHOD_POST);
    char content_type[96];
    snprintf(content_type, sizeof(content_type), "multipart/form-data; boundary=%s", boundary);
    esp_http_client_set_header(client, "Content-Type", content_type);
    size_t total = (size_t)head_len + wire_length + strlen(tail);
    bool ok = esp_http_client_open(client, total) == ESP_OK;
    if (ok) ok = write_all(client, head, head_len);
    if (ok) ok = write_all(client, wire, wire_length);
    if (ok) ok = write_all(client, tail, strlen(tail));
    if (ok) {
        esp_http_client_fetch_headers(client);
        int status = esp_http_client_get_status_code(client);
        ok = status >= 200 && status < 300;
        ESP_LOGI(TAG, "voice upload status=%d bytes=%u", status, (unsigned)length);
    }
    esp_http_client_cleanup(client);
    atomic_fetch_add(&audio_raw_bytes, length);
    atomic_fetch_add(&audio_wire_bytes, wire_length);
    free(compressed);
    return ok;
}

bool hanmir_report_speaker(const char *command_id, bool ok)
{
    char path[192];
    snprintf(path, sizeof(path), "/api/devices/%s/component-result", CONFIG_HANMIR_DEVICE_ID);
    cJSON *body = cJSON_CreateObject();
    cJSON_AddStringToObject(body, "component", "speaker");
    cJSON_AddStringToObject(body, "status", ok ? "ok" : "error");
    if (command_id && command_id[0]) cJSON_AddStringToObject(body, "command_id", command_id);
    bool result = post_json(path, body);
    cJSON_Delete(body);
    return result;
}
