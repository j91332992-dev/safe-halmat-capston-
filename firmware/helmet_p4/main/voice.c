#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "hanmir.h"
#include "driver/i2s_std.h"
#include "esp_afe_config.h"
#include "esp_afe_sr_iface.h"
#include "esp_afe_sr_models.h"
#include "esp_check.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_wn_iface.h"
#include "esp_ns.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "model_path.h"

#ifndef CONFIG_HANMIR_ENABLE_NS
#define CONFIG_HANMIR_ENABLE_NS 0
#endif
#ifndef CONFIG_HANMIR_ENABLE_WAKENET
#define CONFIG_HANMIR_ENABLE_WAKENET 0
#endif

#define SAMPLE_RATE 16000
#define MAX_CLIP_BYTES (SAMPLE_RATE * 2 * 5)
#define END_SILENCE_MS 500
#define PRE_ROLL_BYTES (SAMPLE_RATE * 2 * 300 / 1000)

typedef struct { uint8_t *wav; size_t length; } voice_clip_t;
static const char *TAG = "hanmir_voice";
static i2s_chan_handle_t mic;
static const esp_afe_sr_iface_t *afe;
static esp_afe_sr_data_t *afe_data;
static QueueHandle_t upload_queue;
static volatile bool playback_active;
static volatile bool voice_ready, ns_ready;
bool hanmir_voice_ready(void) { return voice_ready; }
bool hanmir_voice_ns_ready(void) { return ns_ready; }

void hanmir_voice_set_playback(bool playing) { playback_active = playing; }

static void le16(uint8_t *p, uint16_t value) { p[0] = value; p[1] = value >> 8; }
static void le32(uint8_t *p, uint32_t value)
{
    for (int i = 0; i < 4; ++i) p[i] = (value >> (8 * i)) & 0xff;
}

static void wav_header(uint8_t *p, size_t pcm_bytes)
{
    memcpy(p, "RIFF", 4); le32(p + 4, pcm_bytes + 36);
    memcpy(p + 8, "WAVEfmt ", 8); le32(p + 16, 16);
    le16(p + 20, 1); le16(p + 22, 1); le32(p + 24, SAMPLE_RATE);
    le32(p + 28, SAMPLE_RATE * 2); le16(p + 32, 2); le16(p + 34, 16);
    memcpy(p + 36, "data", 4); le32(p + 40, pcm_bytes);
}

static void feed_task(void *arg)
{
    int samples = afe->get_feed_chunksize(afe_data);
    int32_t *raw = heap_caps_malloc(samples * 4, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    int16_t *pcm = heap_caps_malloc(samples * 2, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    if (!raw || !pcm) { ESP_LOGE(TAG, "feed allocation failed"); vTaskDelete(NULL); }
    ns_handle_t ns = NULL;
    int16_t ns_input[160], ns_output[160];
    int ns_fill = 0, afe_fill = 0;
    int peak = 0;
    TickType_t last_level = xTaskGetTickCount();
    if (CONFIG_HANMIR_ENABLE_NS) {
        ns = ns_pro_create(10, 0, SAMPLE_RATE);
        ns_ready = ns != NULL;
        ESP_LOGI(TAG, "external WebRTC NS %s; frame=%d samples", ns ? "ready" : "unavailable", samples);
    }
    for (;;) {
        size_t read = 0;
        if (i2s_channel_read(mic, raw, samples * 4, &read, pdMS_TO_TICKS(1000)) == ESP_OK &&
            read == samples * 4) {
            for (int i = 0; i < samples; ++i) {
                int value = (int16_t)(raw[i] >> 16);
                if (value < 0) value = -value;
                if (value > peak) peak = value;
            }
            if (xTaskGetTickCount() - last_level >= pdMS_TO_TICKS(5000)) {
                ESP_LOGI(TAG, "mic PCM peak=%d/32768", peak);
                peak = 0;
                last_level = xTaskGetTickCount();
            }
            if (!ns) {
                for (int i = 0; i < samples; ++i) pcm[i] = (int16_t)(raw[i] >> 16);
                afe->feed(afe_data, pcm);
                continue;
            }
            // WebRTC NS requires 10 ms frames; AFE chunk sizes need not be a multiple of 160.
            for (int i = 0; i < samples; ++i) {
                ns_input[ns_fill++] = (int16_t)(raw[i] >> 16);
                if (ns_fill != 160) continue;
                ns_process(ns, ns_input, ns_output);
                ns_fill = 0;
                for (int j = 0; j < 160; ++j) {
                    pcm[afe_fill++] = ns_output[j];
                    if (afe_fill == samples) { afe->feed(afe_data, pcm); afe_fill = 0; }
                }
            }
        }
    }
}

static void fetch_task(void *arg)
{
    int chunk_samples = afe->get_fetch_chunksize(afe_data);
    uint8_t *current = NULL;
    size_t used = 0;
    uint8_t *pre_roll = heap_caps_malloc(PRE_ROLL_BYTES, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    size_t pre_next = 0, pre_count = 0;
    if (!pre_roll) { ESP_LOGE(TAG, "pre-roll allocation failed"); vTaskDelete(NULL); }
    unsigned silence_ms = 0;
    unsigned chunk_ms = (unsigned)(chunk_samples * 1000 / SAMPLE_RATE);
    for (;;) {
        afe_fetch_result_t *result = afe->fetch(afe_data);
        if (!result || !result->data || result->ret_value == ESP_FAIL) {
            ESP_LOGW(TAG, "AFE fetch failed");
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }
        if (hanmir_call_active()) hanmir_call_feed(result->data, chunk_samples);
        if (playback_active || hanmir_call_active()) {
            free(current);
            current = NULL;
            used = 0;
            silence_ms = 0;
            pre_count = 0;
            pre_next = 0;
            continue;
        }
        if (result->wakeup_state == WAKENET_DETECTED) {
            ESP_LOGW(TAG, "WakeNet hit logged only; Korean model needs validation");
        }
        bool speech = result->vad_state == VAD_SPEECH;
        if (speech && !current) {
            current = heap_caps_malloc(MAX_CLIP_BYTES + 44, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
            used = 0;
            silence_ms = 0;
            if (!current) ESP_LOGE(TAG, "voice clip allocation failed");
            if (current && pre_count) {
                size_t start = (pre_next + PRE_ROLL_BYTES - pre_count) % PRE_ROLL_BYTES;
                for (size_t i = 0; i < pre_count; ++i) {
                    current[44 + i] = pre_roll[(start + i) % PRE_ROLL_BYTES];
                }
                used = pre_count;
            }
        }
        size_t bytes = (size_t)chunk_samples * 2;
        if (current && used + bytes <= MAX_CLIP_BYTES) {
            memcpy(current + 44 + used, result->data, bytes);
            used += bytes;
        }
        const uint8_t *pcm_bytes = (const uint8_t *)result->data;
        for (size_t i = 0; i < bytes; ++i) {
            pre_roll[pre_next] = pcm_bytes[i];
            pre_next = (pre_next + 1) % PRE_ROLL_BYTES;
            if (pre_count < PRE_ROLL_BYTES) pre_count++;
        }
        if (!current) continue;
        silence_ms = speech ? 0 : silence_ms + chunk_ms;
        if (silence_ms < END_SILENCE_MS && used + bytes <= MAX_CLIP_BYTES) continue;
        if (used >= SAMPLE_RATE * 2 / 5) {
            wav_header(current, used);
            voice_clip_t clip = {.wav = current, .length = used + 44};
            if (xQueueSend(upload_queue, &clip, 0) != pdTRUE) {
                ESP_LOGE(TAG, "voice queue full; clip not delivered");
                free(current);
            }
        } else free(current);
        current = NULL;
        used = 0;
    }
}

static void upload_task(void *arg)
{
    voice_clip_t clip;
    for (;;) {
        if (xQueueReceive(upload_queue, &clip, portMAX_DELAY) != pdTRUE) continue;
        if (hanmir_call_active()) { free(clip.wav); continue; }
        for (int attempt = 0; attempt < 3; ++attempt) {
            if (hanmir_audio_upload_wav(clip.wav, clip.length)) break;
            ESP_LOGW(TAG, "voice upload retry %d/3", attempt + 1);
            vTaskDelay(pdMS_TO_TICKS(1000 * (attempt + 1)));
        }
        free(clip.wav);
    }
}

esp_err_t hanmir_voice_start(void)
{
    if (CONFIG_HANMIR_MIC_BCLK_GPIO < 0 || CONFIG_HANMIR_MIC_WS_GPIO < 0 ||
        CONFIG_HANMIR_MIC_DATA_GPIO < 0) {
        ESP_LOGW(TAG, "Microphone GPIOs unverified; set them in menuconfig after board inspection");
        return ESP_ERR_INVALID_ARG;
    }
    i2s_chan_config_t channel = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    ESP_RETURN_ON_ERROR(i2s_new_channel(&channel, NULL, &mic), TAG, "I2S channel");
    i2s_std_config_t std = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(SAMPLE_RATE),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {.mclk = I2S_GPIO_UNUSED,
                     .bclk = (gpio_num_t)CONFIG_HANMIR_MIC_BCLK_GPIO,
                     .ws = (gpio_num_t)CONFIG_HANMIR_MIC_WS_GPIO,
                     .dout = I2S_GPIO_UNUSED,
                     .din = (gpio_num_t)CONFIG_HANMIR_MIC_DATA_GPIO},
    };
    std.slot_cfg.slot_mask = I2S_STD_SLOT_LEFT;
    ESP_RETURN_ON_ERROR(i2s_channel_init_std_mode(mic, &std), TAG, "I2S std mode");
    ESP_RETURN_ON_ERROR(i2s_channel_enable(mic), TAG, "I2S enable");
    srmodel_list_t *models = NULL;
#if CONFIG_HANMIR_ENABLE_WAKENET
    models = esp_srmodel_init("model");
    if (!models) return ESP_ERR_NOT_FOUND;
#endif
    afe_config_t *config = afe_config_init("M", models, AFE_TYPE_SR, AFE_MODE_LOW_COST);
    if (!config) return ESP_FAIL;
    config->aec_init = false; // Requires a real MAX98357A PCM playback reference.
    config->vad_init = true;
    config->vad_model_name = NULL;
    // Use the standalone WebRTC frontend: this AFE build rejects the "WEBRTC" model name.
    config->ns_init = false;
    config->wakenet_init = CONFIG_HANMIR_ENABLE_WAKENET;
#if CONFIG_HANMIR_ENABLE_WAKENET
    if (!config->wakenet_model_name) { afe_config_free(config); return ESP_ERR_NOT_FOUND; }
#endif
    afe = esp_afe_handle_from_config(config);
    afe_data = afe ? afe->create_from_config(config) : NULL;
    afe_config_free(config);
    if (!afe_data) return ESP_FAIL;
    upload_queue = xQueueCreate(3, sizeof(voice_clip_t));
    if (!upload_queue) return ESP_ERR_NO_MEM;
    if (xTaskCreatePinnedToCore(feed_task, "mic_feed", 6144, NULL, 5, NULL, 0) != pdPASS ||
        xTaskCreatePinnedToCore(fetch_task, "voice_vad", 8192, NULL, 5, NULL, 1) != pdPASS ||
        xTaskCreate(upload_task, "voice_upload", 6144, NULL, 4, NULL) != pdPASS) return ESP_ERR_NO_MEM;
    ESP_LOGI(TAG, "INMP441 + AFE VAD ready; external NS readiness is logged by mic_feed");
    voice_ready = true;
    return ESP_OK;
}
