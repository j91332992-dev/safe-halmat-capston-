#include "hanmir.h"
#include "cJSON.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include <stdio.h>
#include <string.h>

static const char *TAG = "hanmir_fall";
static QueueHandle_t detections;
static portMUX_TYPE fall_mux = portMUX_INITIALIZER_UNLOCKED;
static char response_incident[64];
static int64_t response_until_us;
static bool busy;
static bool speech_started;

void hanmir_fall_voice_started(const char *incident_id)
{
    portENTER_CRITICAL(&fall_mux);
    if (!strcmp(incident_id, response_incident) && esp_timer_get_time() < response_until_us) speech_started = true;
    portEXIT_CRITICAL(&fall_mux);
}

bool hanmir_fall_response_context(char *incident, size_t capacity)
{
    portENTER_CRITICAL(&fall_mux);
    bool ready = response_incident[0] && esp_timer_get_time() < response_until_us;
    if (incident && capacity) strlcpy(incident, ready ? response_incident : "", capacity);
    portEXIT_CRITICAL(&fall_mux);
    return ready;
}

bool hanmir_fall_busy(void)
{
    portENTER_CRITICAL(&fall_mux);
    bool value = busy;
    portEXIT_CRITICAL(&fall_mux);
    return value;
}

int hanmir_fall_remaining_ms(void)
{
    portENTER_CRITICAL(&fall_mux);
    int64_t remaining = (response_until_us - esp_timer_get_time()) / 1000;
    portEXIT_CRITICAL(&fall_mux);
    return remaining > 0 ? (remaining > 8000 ? 8000 : (int)remaining) : 0;
}

void hanmir_fall_detected(const fall_event_t *event)
{
    if (hanmir_call_active()) {
        ESP_LOGI(TAG, "fall ignored: call active");
        return;
    }
    if (hanmir_fall_busy()) return;
    if (!detections || xQueueSend(detections, event, 0) != pdTRUE) {
        ESP_LOGE(TAG, "fall notification queue unavailable/full; local IMU evidence retained");
    }
}

static cJSON *request(const char *path, cJSON *body)
{
    if (!hanmir_network_online() || !CONFIG_HANMIR_SERVER_HOST[0]) return NULL;
    char url[320], authorization[256];
    snprintf(url, sizeof(url), "http://%s:%d%s", CONFIG_HANMIR_SERVER_HOST, CONFIG_HANMIR_SERVER_PORT, path);
    snprintf(authorization, sizeof(authorization), "Bearer %s", CONFIG_HANMIR_CALL_DEVICE_TOKEN);
    esp_http_client_config_t config = {.url = url, .timeout_ms = 2500};
    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (!client) return NULL;
    esp_http_client_set_header(client, "Authorization", authorization);
    char *payload = body ? cJSON_PrintUnformatted(body) : NULL;
    cJSON *result = NULL;
    if (body && !payload) goto done;
    esp_http_client_set_method(client, body ? HTTP_METHOD_POST : HTTP_METHOD_GET);
    if (body) esp_http_client_set_header(client, "Content-Type", "application/json");
    size_t length = payload ? strlen(payload) : 0;
    if (esp_http_client_open(client, length) != ESP_OK) goto done;
    size_t written = 0;
    while (written < length) {
        int count = esp_http_client_write(client, payload + written, length - written);
        if (count <= 0) goto done;
        written += count;
    }
    if (esp_http_client_fetch_headers(client) < 0) goto done;
    int status = esp_http_client_get_status_code(client);
    if (status < 200 || status >= 300) goto done;
    char response[2048];
    int used = 0, count;
    while (used < sizeof(response) - 1 &&
           (count = esp_http_client_read(client, response + used, sizeof(response) - 1 - used)) > 0) used += count;
    response[used] = 0;
    result = cJSON_ParseWithLength(response, used);
done:
    cJSON_free(payload);
    esp_http_client_cleanup(client);
    return result;
}

static void fall_task(void *arg)
{
    (void)arg;
    uint32_t boot_id = esp_random();
    uint32_t sequence = 0;
    fall_event_t detection;
    for (;;) {
        if (xQueueReceive(detections, &detection, portMAX_DELAY) != pdTRUE) continue;
        if (hanmir_call_active()) continue;
        char detection_id[16], incident_id[64] = "", path[256];
        snprintf(detection_id, sizeof(detection_id), "%08lx%06lx", (unsigned long)boot_id,
                 (unsigned long)(++sequence & 0xffffff));
        portENTER_CRITICAL(&fall_mux);
        speech_started = false;
        portEXIT_CRITICAL(&fall_mux);
        bool prompt_played = false, playback_ok = false, playback_reported = false;
        bool speech_reported = false;
        int64_t playback_end_us = 0;
        for (;;) {
            portENTER_CRITICAL(&fall_mux);
            bool captured_speech = speech_started;
            portEXIT_CRITICAL(&fall_mux);
            cJSON *reply;
            if (!incident_id[0]) {
                if (hanmir_call_active()) break;
                cJSON *body = cJSON_CreateObject();
                cJSON_AddStringToObject(body, "device_id", CONFIG_HANMIR_DEVICE_ID);
                cJSON_AddStringToObject(body, "detection_id", detection_id);
                cJSON_AddNumberToObject(body, "peak_g", detection.peak_g);
                cJSON_AddNumberToObject(body, "peak_rad_s", detection.peak_rad_s);
                cJSON_AddNumberToObject(body, "tilt_deg", detection.tilt_deg);
                cJSON_AddBoolToObject(body, "call_active", false);
                reply = request("/api/falls/detect", body);
                cJSON_Delete(body);
            } else if (prompt_played && !playback_reported) {
                snprintf(path, sizeof(path), "/api/falls/%s/playback", incident_id);
                cJSON *body = cJSON_CreateObject();
                cJSON_AddStringToObject(body, "device_id", CONFIG_HANMIR_DEVICE_ID);
                cJSON_AddBoolToObject(body, "ok", playback_ok);
                int64_t remaining = 8000 - (esp_timer_get_time() - playback_end_us) / 1000;
                cJSON_AddNumberToObject(body, "remaining_ms", remaining > 0 ? remaining : 0);
                reply = request(path, body);
                cJSON_Delete(body);
                playback_reported = reply != NULL;
            } else if (captured_speech && !speech_reported) {
                snprintf(path, sizeof(path), "/api/falls/%s/speech-start", incident_id);
                cJSON *body = cJSON_CreateObject();
                cJSON_AddStringToObject(body, "device_id", CONFIG_HANMIR_DEVICE_ID);
                cJSON_AddBoolToObject(body, "ok", true);
                reply = request(path, body);
                cJSON_Delete(body);
                speech_reported = reply != NULL;
            } else {
                snprintf(path, sizeof(path), "/api/falls/%s?device_id=%s", incident_id, CONFIG_HANMIR_DEVICE_ID);
                reply = request(path, NULL);
            }
            if (reply) {
                if (cJSON_IsTrue(cJSON_GetObjectItem(reply, "ignored"))) {
                    cJSON_Delete(reply);
                    break;
                }
                cJSON *id = cJSON_GetObjectItem(reply, "incident_id");
                cJSON *state = cJSON_GetObjectItem(reply, "state");
                cJSON *audio = cJSON_GetObjectItem(reply, "audio_url");
                if (cJSON_IsString(id)) {
                    strlcpy(incident_id, id->valuestring, sizeof(incident_id));
                    portENTER_CRITICAL(&fall_mux);
                    busy = true;
                    portEXIT_CRITICAL(&fall_mux);
                }
                bool terminal = cJSON_IsString(state) &&
                    (!strcmp(state->valuestring, "emergency") || !strcmp(state->valuestring, "cleared"));
                if (terminal) {
                    portENTER_CRITICAL(&fall_mux);
                    response_incident[0] = 0;
                    response_until_us = 0;
                    busy = false;
                    portEXIT_CRITICAL(&fall_mux);
                    if (cJSON_IsString(audio) && !hanmir_call_active()) {
                        if (!hanmir_speaker_play_url(audio->valuestring)) ESP_LOGE(TAG, "fall result guidance playback failed");
                        cJSON_Delete(reply);
                        break;
                    }
                    if (cJSON_IsTrue(cJSON_GetObjectItem(reply, "result_ready"))) {
                        ESP_LOGE(TAG, "fall result guidance unavailable; administrator state retained");
                        cJSON_Delete(reply);
                        break;
                    }
                    if (hanmir_call_active()) {
                        cJSON_Delete(reply);
                        break;
                    }
                } else if (cJSON_IsString(state) && !strcmp(state->valuestring, "waiting_prompt") &&
                           !prompt_played && cJSON_IsString(audio)) {
                    playback_ok = !hanmir_call_active() && hanmir_speaker_play_url(audio->valuestring);
                    playback_end_us = esp_timer_get_time();
                    prompt_played = true;
                    if (playback_ok) {
                        portENTER_CRITICAL(&fall_mux);
                        strlcpy(response_incident, incident_id, sizeof(response_incident));
                        response_until_us = playback_end_us + 8000000;
                        portEXIT_CRITICAL(&fall_mux);
                    }
                }
                cJSON_Delete(reply);
            }
            vTaskDelay(pdMS_TO_TICKS(250));
        }
        portENTER_CRITICAL(&fall_mux);
        response_incident[0] = 0;
        response_until_us = 0;
        busy = false;
        portEXIT_CRITICAL(&fall_mux);
    }
}

esp_err_t hanmir_fall_start(void)
{
    detections = xQueueCreate(8, sizeof(fall_event_t));
    if (!detections) return ESP_ERR_NO_MEM;
    if (xTaskCreate(fall_task, "fall_client", 8192, NULL, 3, NULL) != pdPASS) {
        vQueueDelete(detections);
        detections = NULL;
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}
