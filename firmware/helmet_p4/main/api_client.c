#include <stdio.h>
#include <string.h>
#include "hanmir.h"
#include "cJSON.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "hanmir_api";

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
    esp_http_client_config_t config = {.url = url, .timeout_ms = 2500};
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
            cJSON_AddStringToObject(body, "firmware_version", "2.0.0-p4-hw-bringup-20261009");
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
        cJSON_AddStringToObject(components, "battery", battery_ready ? "ready" : "unavailable");
        cJSON_AddStringToObject(components, "imu", hanmir_imu_ready() ? "ready" : "unverified");
        float imu_yaw = 0, imu_pitch = 0, imu_roll = 0;
        if (hanmir_imu_orientation(&imu_yaw, &imu_pitch, &imu_roll)) {
            cJSON_AddNumberToObject(components, "imu_yaw_deg", imu_yaw);
            cJSON_AddNumberToObject(components, "imu_pitch_deg", imu_pitch);
            cJSON_AddNumberToObject(components, "imu_roll_deg", imu_roll);
        }
        cJSON_AddStringToObject(components, "speaker", hanmir_speaker_ready() ? "initialized" : "unavailable");
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
        if (!post_json("/api/devices/heartbeat", body)) registered = false;
        cJSON_Delete(body);
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

bool hanmir_audio_upload_wav(const uint8_t *wav, size_t length)
{
    if (!hanmir_network_online() || !wav || length < 44) return false;
    char url[256], head[512];
    make_url(url, sizeof(url), "/api/audio/upload");
    const char *boundary = "hanmirp4voice";
    int head_len = snprintf(head, sizeof(head),
        "--%s\r\nContent-Disposition: form-data; name=\"device_id\"\r\n\r\n%s\r\n"
        "--%s\r\nContent-Disposition: form-data; name=\"worker_id\"\r\n\r\n%s\r\n"
        "--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"speech.wav\"\r\n"
        "Content-Type: audio/wav\r\n\r\n",
        boundary, CONFIG_HANMIR_DEVICE_ID, boundary, CONFIG_HANMIR_WORKER_ID, boundary);
    const char *tail = "\r\n--hanmirp4voice--\r\n";
    if (head_len <= 0 || head_len >= sizeof(head)) return false;
    esp_http_client_config_t config = {.url = url, .timeout_ms = 12000};
    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (!client) return false;
    esp_http_client_set_method(client, HTTP_METHOD_POST);
    char content_type[96];
    snprintf(content_type, sizeof(content_type), "multipart/form-data; boundary=%s", boundary);
    esp_http_client_set_header(client, "Content-Type", content_type);
    size_t total = (size_t)head_len + length + strlen(tail);
    bool ok = esp_http_client_open(client, total) == ESP_OK;
    if (ok) ok = write_all(client, head, head_len);
    if (ok) ok = write_all(client, wav, length);
    if (ok) ok = write_all(client, tail, strlen(tail));
    if (ok) {
        esp_http_client_fetch_headers(client);
        int status = esp_http_client_get_status_code(client);
        ok = status >= 200 && status < 300;
        ESP_LOGI(TAG, "voice upload status=%d bytes=%u", status, (unsigned)length);
    }
    esp_http_client_cleanup(client);
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
