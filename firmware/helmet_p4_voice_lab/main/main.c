// HANMIR P4 microphone/AFE bring-up. No guessed GPIOs or untrained SOS actions.
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include "driver/i2s_std.h"
#include "esp_afe_config.h"
#include "esp_afe_sr_iface.h"
#include "esp_afe_sr_models.h"
#include "esp_err.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_wn_iface.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "mbedtls/base64.h"
#include "model_path.h"
#include "sdkconfig.h"

#ifndef CONFIG_HANMIR_ENABLE_NS
#define CONFIG_HANMIR_ENABLE_NS 0
#endif
#ifndef CONFIG_HANMIR_ENABLE_WAKENET
#define CONFIG_HANMIR_ENABLE_WAKENET 0
#endif

#define AUDIO_SAMPLE_RATE 16000

static const char *TAG = "hanmir_voice_lab";
static i2s_chan_handle_t mic_channel;
static const esp_afe_sr_iface_t *afe_handle;
static esp_afe_sr_data_t *afe_data;

static void microphone_feed_task(void *arg)
{
    const int samples = afe_handle->get_feed_chunksize(afe_data);
    const int channels = afe_handle->get_feed_channel_num(afe_data);
    if (channels != 1 || samples <= 0) {
        ESP_LOGE(TAG, "Expected one 16 kHz microphone channel; got channels=%d samples=%d", channels, samples);
        vTaskDelete(NULL);
        return;
    }

    int32_t *raw = heap_caps_malloc(samples * sizeof(*raw), MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    int16_t *pcm = heap_caps_malloc(samples * sizeof(*pcm), MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    if (!raw || !pcm) {
        ESP_LOGE(TAG, "I2S/AFE feed buffer allocation failed");
        free(raw);
        free(pcm);
        vTaskDelete(NULL);
        return;
    }

    for (;;) {
        size_t bytes_read = 0;
        esp_err_t err = i2s_channel_read(mic_channel, raw, samples * sizeof(*raw), &bytes_read,
                                         pdMS_TO_TICKS(1000));
        if (err != ESP_OK || bytes_read != samples * sizeof(*raw)) {
            ESP_LOGW(TAG, "I2S read failed: %s bytes=%u", esp_err_to_name(err), (unsigned)bytes_read);
            continue;
        }
        // INMP441 has 24-bit samples in a 32-bit I2S slot. Keep the high 16 bits
        // for the 16-bit, mono input required by ESP-SR AFE.
        for (int i = 0; i < samples; ++i) {
            pcm[i] = (int16_t)(raw[i] >> 16);
        }
        afe_handle->feed(afe_data, pcm);
    }
}

static void print_pcm_line(const int16_t *pcm, int samples)
{
#if CONFIG_HANMIR_STREAM_PCM
    const size_t input_bytes = (size_t)samples * sizeof(*pcm);
    const size_t encoded_size = 4 * ((input_bytes + 2) / 3) + 1;
    char *encoded = malloc(encoded_size);
    size_t written = 0;
    if (!encoded) return;
    if (mbedtls_base64_encode((unsigned char *)encoded, encoded_size, &written,
                              (const unsigned char *)pcm, input_bytes) == 0) {
        encoded[written] = '\0';
        printf("PCM:%s\n", encoded);
    }
    free(encoded);
#else
    (void)pcm;
    (void)samples;
#endif
}

static void afe_fetch_task(void *arg)
{
    const int samples = afe_handle->get_fetch_chunksize(afe_data);
    int last_vad_state = -1;
    int64_t last_health_us = 0;
    ESP_LOGI(TAG, "AFE running: sample_rate=%d fetch_samples=%d NS=%d WakeNet=%d",
             AUDIO_SAMPLE_RATE, samples, CONFIG_HANMIR_ENABLE_NS, CONFIG_HANMIR_ENABLE_WAKENET);

    for (;;) {
        afe_fetch_result_t *result = afe_handle->fetch(afe_data);
        if (!result || result->ret_value == ESP_FAIL || !result->data) {
            ESP_LOGE(TAG, "AFE fetch failed");
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }

        if ((int)result->vad_state != last_vad_state) {
            last_vad_state = (int)result->vad_state;
            ESP_LOGI(TAG, "VAD state=%d", last_vad_state);
        }
        if (result->wakeup_state == WAKENET_DETECTED) {
            // This is only a model hit. The selected model must first be proven
            // to recognize '투투스' before any wake/SOS behavior is enabled.
            ESP_LOGW(TAG, "WakeNet model hit: model=%d word=%d",
                     result->wakenet_model_index, result->wake_word_index);
        }

        print_pcm_line(result->data, samples);

        int64_t now_us = esp_timer_get_time();
        if (now_us - last_health_us >= 1000000) {
            last_health_us = now_us;
            int peak = 0;
            for (int i = 0; i < samples; ++i) {
                int value = result->data[i];
                if (value < 0) value = -value;
                if (value > peak) peak = value;
            }
            ESP_LOGI(TAG, "mic_peak=%d free_internal=%u free_psram=%u",
                     peak,
                     (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
                     (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
        }
    }
}

void app_main(void)
{
    if (CONFIG_HANMIR_MIC_BCLK_GPIO < 0 || CONFIG_HANMIR_MIC_WS_GPIO < 0 ||
        CONFIG_HANMIR_MIC_DATA_GPIO < 0) {
        ESP_LOGE(TAG, "Set verified INMP441 BCLK/WS/DATA GPIOs in idf.py menuconfig first");
        return;
    }

    i2s_chan_config_t channel_config = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    ESP_ERROR_CHECK(i2s_new_channel(&channel_config, NULL, &mic_channel));
    i2s_std_config_t microphone_config = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(AUDIO_SAMPLE_RATE),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = (gpio_num_t)CONFIG_HANMIR_MIC_BCLK_GPIO,
            .ws = (gpio_num_t)CONFIG_HANMIR_MIC_WS_GPIO,
            .dout = I2S_GPIO_UNUSED,
            .din = (gpio_num_t)CONFIG_HANMIR_MIC_DATA_GPIO,
        },
    };
    microphone_config.slot_cfg.slot_mask = I2S_STD_SLOT_LEFT;
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(mic_channel, &microphone_config));
    ESP_ERROR_CHECK(i2s_channel_enable(mic_channel));

    srmodel_list_t *models = NULL;
    if (CONFIG_HANMIR_ENABLE_WAKENET) {
        models = esp_srmodel_init("model");
        if (!models) {
            ESP_LOGE(TAG, "WakeNet enabled but no model found in the model partition");
            return;
        }
    }
    afe_config_t *afe_config = afe_config_init("M", models, AFE_TYPE_SR, AFE_MODE_LOW_COST);
    if (!afe_config) {
        ESP_LOGE(TAG, "AFE config creation failed");
        return;
    }
    afe_config->aec_init = false;  // Enable only after speaker PCM reference is wired into AFE.
    afe_config->vad_init = true;
    afe_config->vad_model_name = NULL;  // WebRTC VAD; no extra model download.
    afe_config->ns_init = CONFIG_HANMIR_ENABLE_NS;
    if (CONFIG_HANMIR_ENABLE_NS) {
        afe_config->afe_ns_mode = AFE_NS_MODE_WEBRTC;
        afe_config->ns_model_name = "WEBRTC";
    }
    afe_config->wakenet_init = CONFIG_HANMIR_ENABLE_WAKENET;
    if (CONFIG_HANMIR_ENABLE_WAKENET && !afe_config->wakenet_model_name) {
        ESP_LOGE(TAG, "Select and flash a WakeNet model in ESP Speech Recognition menuconfig");
        afe_config_free(afe_config);
        return;
    }

    afe_handle = esp_afe_handle_from_config(afe_config);
    afe_data = afe_handle ? afe_handle->create_from_config(afe_config) : NULL;
    afe_config_free(afe_config);
    if (!afe_data) {
        ESP_LOGE(TAG, "AFE initialization failed");
        return;
    }

    BaseType_t feed_created = xTaskCreatePinnedToCore(microphone_feed_task, "hanmir_mic", 6144,
                                                      NULL, 5, NULL, 0);
    BaseType_t fetch_created = xTaskCreatePinnedToCore(afe_fetch_task, "hanmir_afe", 8192,
                                                       NULL, 5, NULL, 1);
    if (feed_created != pdPASS || fetch_created != pdPASS) {
        ESP_LOGE(TAG, "Voice lab task creation failed");
    }
}
