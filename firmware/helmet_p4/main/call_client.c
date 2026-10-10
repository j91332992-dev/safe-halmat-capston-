#include <stdio.h>
#include <string.h>
#include "hanmir.h"
#include "cJSON.h"
#include "esp_log.h"
#include "esp_websocket_client.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

// 20 ms, mono 16 kHz PCM16. Bounded queues drop audio instead of building delay.
typedef struct { uint16_t bytes; uint8_t data[640]; } call_frame_t;
static const char *TAG = "hanmir_call";
static QueueHandle_t transmit, receive;
static esp_websocket_client_handle_t client;
static volatile bool active;
static uint8_t incoming[4096];
static bool binary_message;
static bool receiving;
static size_t incoming_used;

bool hanmir_call_active(void) { return active; }

void hanmir_call_interrupt(void)
{
    if (!active) return;
    active = false;
    const char *message = "{\"type\":\"call_stop\"}";
    esp_websocket_client_send_text(client, message, strlen(message), pdMS_TO_TICKS(100));
}

void hanmir_call_feed(const int16_t *pcm, size_t samples)
{
    if (!active || !transmit) return;
    while (samples) {
        size_t count = samples > 320 ? 320 : samples;
        call_frame_t frame = {.bytes = count * 2};
        memcpy(frame.data, pcm, frame.bytes);
        if (xQueueSend(transmit, &frame, 0) != pdTRUE) {
            call_frame_t stale;
            xQueueReceive(transmit, &stale, 0);
            xQueueSend(transmit, &frame, 0);
        }
        pcm += count;
        samples -= count;
    }
}

static void call_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (id == WEBSOCKET_EVENT_DISCONNECTED || id == WEBSOCKET_EVENT_ERROR) {
        active = false;
        receiving = false;
        return;
    }
    if (id == WEBSOCKET_EVENT_CONNECTED) {
        ESP_LOGI(TAG, "call channel connected; server authenticates device");
        return;
    }
    if (id != WEBSOCKET_EVENT_DATA) return;
    esp_websocket_event_data_t *event = data;
    if (event->op_code == 8) { active = false; return; }
    if (event->op_code != 0 && event->op_code != 1 && event->op_code != 2) return;
    if (event->payload_offset == 0) {
        binary_message = event->op_code == 2;
        incoming_used = 0;
        receiving = event->payload_len > 0 && event->payload_len <= sizeof(incoming);
    }
    if (!receiving || event->payload_offset != incoming_used ||
        incoming_used + event->data_len > sizeof(incoming)) { receiving = false; return; }
    memcpy(incoming + incoming_used, event->data_ptr, event->data_len);
    incoming_used += event->data_len;
    if (incoming_used != event->payload_len) return;
    receiving = false;
    if (binary_message) {
        if (!active || incoming_used % 2) return;
        for (size_t offset = 0; offset < incoming_used;) {
            size_t bytes = incoming_used - offset;
            if (bytes > 640) bytes = 640;
            call_frame_t frame = {.bytes = bytes};
            memcpy(frame.data, incoming + offset, bytes);
            if (xQueueSend(receive, &frame, 0) != pdTRUE) {
                call_frame_t stale;
                xQueueReceive(receive, &stale, 0);
                xQueueSend(receive, &frame, 0);
            }
            offset += bytes;
        }
        return;
    }
    cJSON *root = cJSON_ParseWithLength((char *)incoming, incoming_used);
    if (!root) return;
    cJSON *type = cJSON_GetObjectItem(root, "type");
    if (cJSON_IsString(type)) {
        if (!strcmp(type->valuestring, "call_start")) {
            xQueueReset(transmit);
            xQueueReset(receive);
            active = true;
            ESP_LOGI(TAG, "full duplex call started");
        } else if (!strcmp(type->valuestring, "call_stop")) {
            active = false;
            ESP_LOGI(TAG, "call stopped");
        }
    }
    cJSON_Delete(root);
}

static void transmit_task(void *arg)
{
    call_frame_t frame;
    for (;;) {
        if (xQueueReceive(transmit, &frame, pdMS_TO_TICKS(100)) == pdTRUE && active &&
            esp_websocket_client_is_connected(client)) {
            if (esp_websocket_client_send_bin(client, (char *)frame.data, frame.bytes,
                    pdMS_TO_TICKS(20)) != frame.bytes) {
                // A partial audio frame cannot be replayed without corrupting its timing.
                active = false;
                esp_websocket_client_stop(client);
                esp_websocket_client_start(client);
            }
        }
    }
}

static void playback_task(void *arg)
{
    bool playing = false;
    call_frame_t frame;
    for (;;) {
        if (active && !playing) playing = hanmir_speaker_call_begin();
        if (!active && playing) { hanmir_speaker_call_end(); playing = false; }
        if (xQueueReceive(receive, &frame, pdMS_TO_TICKS(20)) == pdTRUE && active && playing) {
            if (!hanmir_speaker_call_write(frame.data, frame.bytes)) active = false;
        }
    }
}

esp_err_t hanmir_call_start(void)
{
    if (!CONFIG_HANMIR_CALL_DEVICE_TOKEN[0] || !CONFIG_HANMIR_SERVER_HOST[0]) {
        ESP_LOGW(TAG, "call channel disabled: configure device token and server");
        return ESP_OK;
    }
    if (!hanmir_voice_ready() || !hanmir_speaker_ready()) return ESP_ERR_INVALID_STATE;
    transmit = xQueueCreate(6, sizeof(call_frame_t));
    receive = xQueueCreate(6, sizeof(call_frame_t));
    if (!transmit || !receive) return ESP_ERR_NO_MEM;
    static char uri[256], headers[256];
    snprintf(uri, sizeof(uri), "ws://%s:%d/ws/call/device/%s", CONFIG_HANMIR_SERVER_HOST,
             CONFIG_HANMIR_SERVER_PORT, CONFIG_HANMIR_DEVICE_ID);
    snprintf(headers, sizeof(headers), "Authorization: Bearer %s\r\n", CONFIG_HANMIR_CALL_DEVICE_TOKEN);
    esp_websocket_client_config_t config = {.uri = uri, .headers = headers,
        .reconnect_timeout_ms = 2000, .buffer_size = 4096, .task_stack = 6144};
    client = esp_websocket_client_init(&config);
    if (!client) return ESP_ERR_NO_MEM;
    esp_websocket_register_events(client, WEBSOCKET_EVENT_ANY, call_event, NULL);
    if (xTaskCreate(transmit_task, "call_tx", 4096, NULL, 4, NULL) != pdPASS ||
        xTaskCreate(playback_task, "call_rx", 4096, NULL, 4, NULL) != pdPASS) return ESP_ERR_NO_MEM;
    return esp_websocket_client_start(client);
}
