#include <math.h>
#include <stdio.h>
#include <string.h>
#include "hanmir.h"
#include "driver/i2s_std.h"
#include "esp_check.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "hanmir_speaker";
static i2s_chan_handle_t speaker;
static bool speaker_enabled;

esp_err_t hanmir_speaker_start(void)
{
    if (CONFIG_HANMIR_SPK_BCLK_GPIO < 0 || CONFIG_HANMIR_SPK_WS_GPIO < 0 ||
        CONFIG_HANMIR_SPK_DATA_GPIO < 0) {
        ESP_LOGW(TAG, "Speaker GPIOs not verified; output disabled");
        return ESP_ERR_INVALID_ARG;
    }
    i2s_chan_config_t channel = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_1, I2S_ROLE_MASTER);
    ESP_RETURN_ON_ERROR(i2s_new_channel(&channel, &speaker, NULL), TAG, "I2S TX channel");
    i2s_std_config_t std = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(16000),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {.mclk = I2S_GPIO_UNUSED,
                     .bclk = (gpio_num_t)CONFIG_HANMIR_SPK_BCLK_GPIO,
                     .ws = (gpio_num_t)CONFIG_HANMIR_SPK_WS_GPIO,
                     .dout = (gpio_num_t)CONFIG_HANMIR_SPK_DATA_GPIO,
                     .din = I2S_GPIO_UNUSED},
    };
    std.slot_cfg.slot_mask = I2S_STD_SLOT_LEFT;
    ESP_RETURN_ON_ERROR(i2s_channel_init_std_mode(speaker, &std), TAG, "I2S TX std");
    esp_err_t err = i2s_channel_enable(speaker);
    speaker_enabled = err == ESP_OK;
    return err;
}

bool hanmir_speaker_ready(void) { return speaker_enabled; }

bool hanmir_speaker_tone(int frequency, int duration_ms)
{
    if (!speaker_enabled || frequency < 100 || frequency > 4000 || duration_ms < 1 || duration_ms > 2000) return false;
    hanmir_voice_set_playback(true);
    int16_t pcm[320];
    int total = 16 * duration_ms;
    int produced = 0;
    bool ok = true;
    while (produced < total) {
        int count = total - produced > 320 ? 320 : total - produced;
        for (int i = 0; i < count; ++i) {
            pcm[i] = (int16_t)(sin(2.0 * 3.141592653589793 * frequency * (produced + i) / 16000.0) * 9000.0);
        }
        size_t written = 0;
        if (i2s_channel_write(speaker, pcm, count * 2, &written, 1000) != ESP_OK || written != count * 2) {
            ok = false; break;
        }
        produced += count;
    }
    vTaskDelay(pdMS_TO_TICKS(80));
    hanmir_voice_set_playback(false);
    return ok;
}

bool hanmir_speaker_play_url(const char *path)
{
    if (!speaker_enabled || !path || strncmp(path, "/tts/", 5) != 0 || strlen(path) > 160) return false;
    char url[320];
    snprintf(url, sizeof(url), "http://%s:%d%s", CONFIG_HANMIR_SERVER_HOST,
             CONFIG_HANMIR_SERVER_PORT, path);
    esp_http_client_config_t config = {.url = url, .timeout_ms = 5000};
    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (!client) return false;
    bool ok = esp_http_client_open(client, 0) == ESP_OK;
    if (ok) {
        esp_http_client_fetch_headers(client);
        ok = esp_http_client_get_status_code(client) == 200;
    }
    hanmir_voice_set_playback(true);
    uint8_t buf[1024];
    uint8_t header[44];
    size_t header_read = 0;
    while (ok) {
        int n = esp_http_client_read(client, (char *)buf, sizeof(buf));
        if (n < 0) { ok = false; break; }
        if (n == 0) break;
        int offset = 0;
        if (header_read < sizeof(header)) {
            size_t take = sizeof(header) - header_read;
            if (take > (size_t)n) take = n;
            memcpy(header + header_read, buf, take);
            header_read += take;
            offset = take;
            if (header_read == sizeof(header) &&
                (memcmp(header, "RIFF", 4) || memcmp(header + 8, "WAVE", 4) ||
                 header[22] != 1 || header[23] != 0 ||
                 header[24] != 0x80 || header[25] != 0x3e ||
                 header[34] != 16 || header[35] != 0)) {
                ESP_LOGE(TAG, "TTS must be mono 16 kHz 16-bit PCM WAV");
                ok = false; break;
            }
        }
        if (offset < n) {
            size_t written = 0;
            if (i2s_channel_write(speaker, buf + offset, n - offset, &written, 1000) != ESP_OK ||
                written != n - offset) { ok = false; break; }
        }
    }
    vTaskDelay(pdMS_TO_TICKS(80));
    hanmir_voice_set_playback(false);
    esp_http_client_cleanup(client);
    return ok && header_read == sizeof(header);
}
