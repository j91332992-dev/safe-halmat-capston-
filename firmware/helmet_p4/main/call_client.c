#include <stdio.h>
#include <string.h>
#include <stdatomic.h>
#include "hanmir.h"
#include "cJSON.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_websocket_client.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

// 20 ms, mono 16 kHz PCM16. Bounded queues drop audio instead of building delay.
typedef struct { uint32_t queued_ms; uint16_t bytes; uint8_t data[640]; } call_frame_t;
static const char *TAG = "hanmir_call";
static QueueHandle_t transmit, receive;
static esp_websocket_client_handle_t client;
static volatile bool active;
static uint8_t incoming[4096];
static bool binary_message;
static bool receiving;
static size_t incoming_used;
static atomic_uint tx_queue_drop_bytes, rx_queue_drop_bytes;
static atomic_uint rx_received_bytes, rx_written_bytes, rx_age_drop_bytes, rx_write_error_bytes;
static atomic_uint rx_gap_max_ms, rx_wait_max_ms, rx_write_max_us, rx_queue_high;
static atomic_uint rx_silence_bytes;
static uint32_t rx_last_received_ms;

static void record_max(atomic_uint *value, unsigned sample)
{
    unsigned previous = atomic_load(value);
    while (sample > previous && !atomic_compare_exchange_weak(value, &previous, sample)) {}
}

bool hanmir_call_active(void) { return active; }

void hanmir_call_diagnostics(cJSON *object)
{
    cJSON_AddBoolToObject(object,"active",active);
    cJSON_AddNumberToObject(object,"rx_bytes",atomic_load(&rx_received_bytes));
    cJSON_AddNumberToObject(object,"written_bytes",atomic_load(&rx_written_bytes));
    cJSON_AddNumberToObject(object,"overflow_bytes",atomic_load(&rx_queue_drop_bytes));
    cJSON_AddNumberToObject(object,"aged_bytes",atomic_load(&rx_age_drop_bytes));
    cJSON_AddNumberToObject(object,"write_error_bytes",atomic_load(&rx_write_error_bytes));
    cJSON_AddNumberToObject(object,"silence_bytes",atomic_load(&rx_silence_bytes));
    cJSON_AddNumberToObject(object,"tx_drop_bytes",atomic_load(&tx_queue_drop_bytes));
    cJSON_AddNumberToObject(object,"rx_queue",receive?uxQueueMessagesWaiting(receive):0);
}

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
            if (xQueueReceive(transmit, &stale, 0) == pdTRUE) atomic_fetch_add(&tx_queue_drop_bytes, stale.bytes);
            xQueueSend(transmit, &frame, 0);
        }
        pcm += count;
        samples -= count;
    }
}

static void call_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (id == WEBSOCKET_EVENT_DISCONNECTED || id == WEBSOCKET_EVENT_ERROR) {
        ESP_LOGW(TAG, "call transport event=%ld; auto reconnect", (long)id);
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
        uint32_t now_ms = (uint32_t)(esp_timer_get_time() / 1000);
        if (rx_last_received_ms) record_max(&rx_gap_max_ms, now_ms - rx_last_received_ms);
        rx_last_received_ms = now_ms;
        atomic_fetch_add(&rx_received_bytes, incoming_used);
        for (size_t offset = 0; offset < incoming_used;) {
            size_t bytes = incoming_used - offset;
            if (bytes > 640) bytes = 640;
            call_frame_t frame = {.queued_ms = now_ms, .bytes = bytes};
            memcpy(frame.data, incoming + offset, bytes);
            if (xQueueSend(receive, &frame, 0) != pdTRUE) {
                call_frame_t stale;
                if (xQueueReceive(receive, &stale, 0) == pdTRUE) atomic_fetch_add(&rx_queue_drop_bytes, stale.bytes);
                if (xQueueSend(receive, &frame, 0) != pdTRUE)
                    atomic_fetch_add(&rx_queue_drop_bytes, frame.bytes);
            }
            record_max(&rx_queue_high, uxQueueMessagesWaiting(receive));
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
            rx_last_received_ms = 0;
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
    uint32_t sent = 0, failed = 0, max_us = 0;
    int64_t logged = esp_timer_get_time();
    for (;;) {
        if (xQueueReceive(transmit, &frame, pdMS_TO_TICKS(100)) == pdTRUE && active &&
            esp_websocket_client_is_connected(client)) {
            int64_t begin = esp_timer_get_time();
            int result = esp_websocket_client_send_bin(client, (char *)frame.data, frame.bytes,
                                                      pdMS_TO_TICKS(1500));
            uint32_t elapsed = (uint32_t)(esp_timer_get_time() - begin);
            if (elapsed > max_us) max_us = elapsed;
            if (result == frame.bytes) {
                sent++;
            } else {
                failed++;
                xQueueReset(transmit); // Drop stale audio; never replay an uncertain frame.
                ESP_LOGW(TAG, "call TX failed result=%d expected=%u elapsed_us=%lu connected=%d",
                         result, (unsigned)frame.bytes, (unsigned long)elapsed,
                         esp_websocket_client_is_connected(client));
                // The websocket library aborts/reconnects actual transport failures.
                // A lock timeout must not trigger a second stop/start race here.
            }
        }
        if (esp_timer_get_time() - logged >= 5000000) {
            ESP_LOGI(TAG, "call TX stats sent=%lu failed=%lu max_us=%lu active=%d connected=%d stack_free_min=%u",
                     (unsigned long)sent, (unsigned long)failed, (unsigned long)max_us,
                     active, esp_websocket_client_is_connected(client),
                     (unsigned)uxTaskGetStackHighWaterMark(NULL));
            ESP_LOGI(TAG, "call queue drops tx_bytes=%u rx_bytes=%u",
                     (unsigned)atomic_load(&tx_queue_drop_bytes), (unsigned)atomic_load(&rx_queue_drop_bytes));
            ESP_LOGI(TAG, "call RX metrics received=%u written=%u overflow=%u aged=%u write_error=%u queue_high=%u gap_max_ms=%u wait_max_ms=%u i2s_max_us=%u",
                     (unsigned)atomic_load(&rx_received_bytes), (unsigned)atomic_load(&rx_written_bytes),
                     (unsigned)atomic_load(&rx_queue_drop_bytes), (unsigned)atomic_load(&rx_age_drop_bytes),
                     (unsigned)atomic_load(&rx_write_error_bytes), (unsigned)atomic_exchange(&rx_queue_high, 0),
                     (unsigned)atomic_exchange(&rx_gap_max_ms, 0), (unsigned)atomic_exchange(&rx_wait_max_ms, 0),
                     (unsigned)atomic_exchange(&rx_write_max_us, 0));
            sent = failed = max_us = 0;
            logged = esp_timer_get_time();
        }
    }
}

static void playback_task(void *arg)
{
    bool playing = false;
    bool primed=false, fade_in=true;
    int16_t tail=0;
    call_frame_t frame;
    size_t bytes_received = 0;
    int peak = 0;
    TickType_t last_log = 0;
    for (;;) {
        if (active && !playing) {
            playing = hanmir_speaker_call_begin();
            if (playing) { bytes_received = 0; peak = 0; last_log = xTaskGetTickCount(); primed=false;fade_in=true;tail=0; }
        }
        if (!active && playing) { hanmir_speaker_call_end(); playing = false; }
        if (active && playing && !primed) {
            if (uxQueueMessagesWaiting(receive)>=3) primed=true;
            else {
                int16_t quiet[320]={0};
                for(int i=0;i<32;i++)quiet[i]=(int16_t)((int32_t)tail*(31-i)/32);
                if (!hanmir_speaker_call_write((uint8_t*)quiet,sizeof(quiet))) active=false;
                atomic_fetch_add(&rx_silence_bytes,sizeof(quiet));tail=0;
                continue;
            }
        }
        if (xQueueReceive(receive, &frame, pdMS_TO_TICKS(20)) == pdTRUE && active && playing) {
            uint32_t wait_ms = (uint32_t)(esp_timer_get_time() / 1000) - frame.queued_ms;
            record_max(&rx_wait_max_ms, wait_ms);
            // Bound latency independently of queue capacity. Never replay old speech.
            if (wait_ms > 200) {
                atomic_fetch_add(&rx_age_drop_bytes, frame.bytes);
                continue;
            }
            bytes_received += frame.bytes;
            // Call-only headroom; TTS/wake playback and microphone PCM are unchanged.
            int16_t *pcm=(int16_t*)frame.data;
            for(unsigned i=0;i<frame.bytes/2;i++) {
                int32_t v=(int32_t)pcm[i]*3/4;
                if(fade_in && i<32)v=v*(int32_t)i/32;
                pcm[i]=(int16_t)v;
            }
            fade_in=false;
            tail=pcm[frame.bytes/2-1];
            for (size_t i = 0; i + 1 < frame.bytes; i += 2) {
                int value = (int16_t)(frame.data[i] | (frame.data[i + 1] << 8));
                if (value < 0) value = -value;
                if (value > peak) peak = value;
            }
            int64_t write_started = esp_timer_get_time();
            bool written = hanmir_speaker_call_write(frame.data, frame.bytes);
            record_max(&rx_write_max_us, (unsigned)(esp_timer_get_time() - write_started));
            if (!written) {
                atomic_fetch_add(&rx_write_error_bytes, frame.bytes);
                ESP_LOGE(TAG, "call speaker I2S write failed");
                active = false;
            } else {
                atomic_fetch_add(&rx_written_bytes, frame.bytes);
            }
            if (xTaskGetTickCount() - last_log >= pdMS_TO_TICKS(2000)) {
                ESP_LOGI(TAG, "call RX PCM bytes=%u peak=%d/32768 speaker_write=ok", (unsigned)bytes_received, peak);
                bytes_received = 0; peak = 0; last_log = xTaskGetTickCount();
            }
        } else if (active && playing) {primed=false;fade_in=true;}
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
    receive = xQueueCreate(12, sizeof(call_frame_t)); // 240ms capacity; 200ms age cap still applies.
    if (!transmit || !receive) return ESP_ERR_NO_MEM;
    static char uri[256], headers[256];
    snprintf(uri, sizeof(uri), "ws://%s:%d/ws/call/device/%s", CONFIG_HANMIR_SERVER_HOST,
             CONFIG_HANMIR_SERVER_PORT, CONFIG_HANMIR_DEVICE_ID);
    snprintf(headers, sizeof(headers), "Authorization: Bearer %s\r\n", CONFIG_HANMIR_CALL_DEVICE_TOKEN);
    esp_websocket_client_config_t config = {.uri = uri, .headers = headers,
        .reconnect_timeout_ms = 1000, .network_timeout_ms = 1000, .buffer_size = 4096, .task_stack = 6144};
    client = esp_websocket_client_init(&config);
    if (!client) return ESP_ERR_NO_MEM;
    esp_websocket_register_events(client, WEBSOCKET_EVENT_ANY, call_event, NULL);
    if (xTaskCreate(transmit_task, "call_tx", 8192, NULL, 4, NULL) != pdPASS ||
        // WebSocket callbacks run at priority 5. Let ready I2S playback drain
        // promptly between back-to-back incoming packets; it blocks on DMA/queue.
        xTaskCreate(playback_task, "call_rx", 4096, NULL, 6, NULL) != pdPASS) return ESP_ERR_NO_MEM;
    return esp_websocket_client_start(client);
}
