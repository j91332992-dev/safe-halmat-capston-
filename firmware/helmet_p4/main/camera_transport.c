#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "hanmir.h"
#include "esp_heap_caps.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "esp_websocket_client.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#ifndef CONFIG_HANMIR_CAMERA_HTTP_BASELINE
#define CONFIG_HANMIR_CAMERA_HTTP_BASELINE 0
#endif

typedef struct {
    uint8_t *jpeg;
    size_t length;
    uint16_t width;
    uint16_t height;
    uint64_t id;
} camera_frame_t;

static const char *TAG = "hanmir_camera_tx";
static QueueHandle_t latest_frame;
static esp_websocket_client_handle_t client;
static uint64_t next_id;
static uint32_t dropped;

static bool write_all(esp_http_client_handle_t http, const uint8_t *data, size_t length)
{
    while (length) {
        int n = esp_http_client_write(http, (const char *)data, length);
        if (n <= 0) return false;
        data += n;
        length -= n;
    }
    return true;
}

static bool post_baseline(const camera_frame_t *frame)
{
    char url[256], head[640];
    snprintf(url, sizeof(url), "http://%s:%d/api/camera/frame",
             CONFIG_HANMIR_SERVER_HOST, CONFIG_HANMIR_SERVER_PORT);
    const char *boundary = "hanmirp4camera";
    int head_len = snprintf(head, sizeof(head),
        "--%s\r\nContent-Disposition: form-data; name=\"device_id\"\r\n\r\n%s\r\n"
        "--%s\r\nContent-Disposition: form-data; name=\"worker_id\"\r\n\r\n%s\r\n"
        "--%s\r\nContent-Disposition: form-data; name=\"helmet_id\"\r\n\r\n%s\r\n"
        "--%s\r\nContent-Disposition: form-data; name=\"frame_id\"\r\n\r\n%llu\r\n"
        "--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"frame.jpg\"\r\n"
        "Content-Type: image/jpeg\r\n\r\n",
        boundary, CONFIG_HANMIR_DEVICE_ID, boundary, CONFIG_HANMIR_WORKER_ID,
        boundary, CONFIG_HANMIR_HELMET_ID, boundary, (unsigned long long)frame->id, boundary);
    const char *tail = "\r\n--hanmirp4camera--\r\n";
    if (head_len <= 0 || head_len >= sizeof(head)) return false;
    esp_http_client_config_t config = {.url = url, .timeout_ms = 1200};
    esp_http_client_handle_t http = esp_http_client_init(&config);
    if (!http) return false;
    esp_http_client_set_method(http, HTTP_METHOD_POST);
    esp_http_client_set_header(http, "Content-Type", "multipart/form-data; boundary=hanmirp4camera");
    bool ok = esp_http_client_open(http, (size_t)head_len + frame->length + strlen(tail)) == ESP_OK;
    if (ok) ok = write_all(http, (const uint8_t *)head, head_len);
    if (ok) ok = write_all(http, frame->jpeg, frame->length);
    if (ok) ok = write_all(http, (const uint8_t *)tail, strlen(tail));
    if (ok) {
        esp_http_client_fetch_headers(http);
        int status = esp_http_client_get_status_code(http);
        ok = status >= 200 && status < 300;
    }
    esp_http_client_cleanup(http);
    return ok;
}

bool hanmir_camera_submit_jpeg(const uint8_t *jpeg, size_t length, uint16_t width, uint16_t height)
{
    if (!latest_frame || !jpeg || length < 4 || length > CONFIG_HANMIR_CAMERA_MAX_BYTES ||
        width == 0 || height == 0 || jpeg[0] != 0xff || jpeg[1] != 0xd8 ||
        jpeg[length - 2] != 0xff || jpeg[length - 1] != 0xd9) return false;
    camera_frame_t frame = {.length = length, .width = width, .height = height, .id = ++next_id};
    frame.jpeg = heap_caps_malloc(length, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!frame.jpeg) return false;
    memcpy(frame.jpeg, jpeg, length);
    camera_frame_t old;
    if (xQueueReceive(latest_frame, &old, 0) == pdTRUE) {
        free(old.jpeg);
        dropped++;
    }
    if (xQueueSend(latest_frame, &frame, 0) != pdTRUE) {
        free(frame.jpeg);
        dropped++;
        return false;
    }
    return true;
}

static void put_u64_be(uint8_t *target, uint64_t value)
{
    for (int i = 7; i >= 0; --i) { target[i] = value & 0xff; value >>= 8; }
}

static void sender_task(void *arg)
{
    camera_frame_t frame;
    for (;;) {
        if (!hanmir_network_online() ||
            (!CONFIG_HANMIR_CAMERA_HTTP_BASELINE && (!client || !esp_websocket_client_is_connected(client)))) {
            vTaskDelay(pdMS_TO_TICKS(200));
            continue;
        }
        if (xQueueReceive(latest_frame, &frame, pdMS_TO_TICKS(500)) != pdTRUE) continue;
        if (CONFIG_HANMIR_CAMERA_HTTP_BASELINE) {
            if (!post_baseline(&frame)) dropped++;
            free(frame.jpeg);
            continue;
        }
        uint8_t *packet = heap_caps_malloc(frame.length + 16, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
        if (!packet) { free(frame.jpeg); dropped++; continue; }
        memcpy(packet, "HMR2", 4);
        put_u64_be(packet + 4, frame.id);
        packet[12] = frame.width >> 8;
        packet[13] = frame.width & 0xff;
        packet[14] = frame.height >> 8;
        packet[15] = frame.height & 0xff;
        memcpy(packet + 16, frame.jpeg, frame.length);
        int sent = esp_websocket_client_send_bin(client, (const char *)packet, frame.length + 16,
                                                  pdMS_TO_TICKS(600));
        if (sent != (int)(frame.length + 16)) {
            dropped++;
            ESP_LOGW(TAG, "send failed frame=%llu bytes=%d", (unsigned long long)frame.id, sent);
        }
        free(packet);
        free(frame.jpeg);
    }
}

esp_err_t hanmir_camera_transport_start(void)
{
    latest_frame = xQueueCreate(1, sizeof(camera_frame_t));
    if (!latest_frame) return ESP_ERR_NO_MEM;
    if (!CONFIG_HANMIR_SERVER_HOST[0] ||
        (!CONFIG_HANMIR_CAMERA_HTTP_BASELINE && !CONFIG_HANMIR_CAMERA_TOKEN[0])) {
        ESP_LOGW(TAG, "Set server host and camera token to enable binary camera stream");
        return ESP_OK;
    }
    if (CONFIG_HANMIR_CAMERA_HTTP_BASELINE) {
        return xTaskCreate(sender_task, "camera_tx", 6144, NULL, 2, NULL) == pdPASS ? ESP_OK : ESP_ERR_NO_MEM;
    }
    static char uri[320];
    static char headers[256];
    snprintf(uri, sizeof(uri), "ws://%s:%d/api/camera/stream/%s?worker_id=%s&helmet_id=%s",
             CONFIG_HANMIR_SERVER_HOST, CONFIG_HANMIR_SERVER_PORT, CONFIG_HANMIR_DEVICE_ID,
             CONFIG_HANMIR_WORKER_ID, CONFIG_HANMIR_HELMET_ID);
    snprintf(headers, sizeof(headers), "X-Hanmir-Camera-Token: %s\r\n", CONFIG_HANMIR_CAMERA_TOKEN);
    esp_websocket_client_config_t config = {.uri = uri, .reconnect_timeout_ms = 2000,
                                             .network_timeout_ms = 1500, .headers = headers};
    client = esp_websocket_client_init(&config);
    if (!client) return ESP_ERR_NO_MEM;
    esp_err_t err = esp_websocket_client_start(client);
    if (err != ESP_OK) return err;
    if (xTaskCreate(sender_task, "camera_tx", 6144, NULL, 2, NULL) != pdPASS) return ESP_ERR_NO_MEM;
    return ESP_OK;
}

bool hanmir_camera_connected(void)
{
    return CONFIG_HANMIR_CAMERA_HTTP_BASELINE ? hanmir_network_online() :
           (client && esp_websocket_client_is_connected(client));
}

uint32_t hanmir_camera_dropped(void) { return dropped; }
