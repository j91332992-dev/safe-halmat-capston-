#include <math.h>
#include <stdio.h>
#include <string.h>
#include "hanmir.h"
#include "driver/i2s_std.h"
#include "esp_check.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"

static const char *TAG = "hanmir_speaker";
static i2s_chan_handle_t speaker;
static bool speaker_enabled;
static SemaphoreHandle_t playback_lock;

esp_err_t hanmir_speaker_start(void)
{
    if (CONFIG_HANMIR_SPK_BCLK_GPIO < 0 || CONFIG_HANMIR_SPK_WS_GPIO < 0 ||
        CONFIG_HANMIR_SPK_DATA_GPIO < 0) {
        ESP_LOGW(TAG, "Speaker GPIOs not verified; output disabled");
        return ESP_ERR_INVALID_ARG;
    }
    i2s_chan_config_t channel = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_1, I2S_ROLE_MASTER);
    // Complete 10 ms DMA blocks when receiving 20 ms call packets.
    // The default 511-frame blocks can be only partly filled by short packets.
    channel.dma_frame_num = 160;
    channel.dma_desc_num = 6;
    channel.auto_clear_after_cb = true;
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
    // Stay silent at boot. Enable TX only while handling a playback command.
    speaker_enabled = true;
    playback_lock = xSemaphoreCreateMutex();
    if (!playback_lock) return ESP_ERR_NO_MEM;
    ESP_LOGI(TAG, "I2S TX ready port=1 BCLK=%d WS=%d DATA=%d rate=16000 bits=16 mono=left",
             CONFIG_HANMIR_SPK_BCLK_GPIO, CONFIG_HANMIR_SPK_WS_GPIO, CONFIG_HANMIR_SPK_DATA_GPIO);
    return ESP_OK;
}

bool hanmir_speaker_ready(void) { return speaker_enabled; }

static bool begin_playback(void)
{
    if (xSemaphoreTake(playback_lock, pdMS_TO_TICKS(200)) != pdTRUE) {
        ESP_LOGE(TAG, "playback lock timeout"); return false;
    }
    esp_err_t err = i2s_channel_enable(speaker);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "I2S enable failed: %s", esp_err_to_name(err));
        xSemaphoreGive(playback_lock); return false;
    }
    hanmir_voice_set_playback(true);
    return true;
}

static void end_playback(void)
{
    // Allow the queued PCM tail to finish before stopping the I2S clocks.
    vTaskDelay(pdMS_TO_TICKS(120));
    i2s_channel_disable(speaker);
    hanmir_voice_set_playback(false);
    xSemaphoreGive(playback_lock);
}

bool hanmir_speaker_call_begin(void) { return speaker_enabled && begin_playback(); }
bool hanmir_speaker_call_write(const uint8_t *pcm, size_t bytes)
{
    size_t written = 0;
    return i2s_channel_write(speaker, pcm, bytes, &written, 100) == ESP_OK && written == bytes;
}
void hanmir_speaker_call_end(void) { end_playback(); }

bool hanmir_speaker_tone(int frequency, int duration_ms)
{
    if (!speaker_enabled || frequency < 100 || frequency > 4000 || duration_ms < 1 || duration_ms > 2000) return false;
    if (!begin_playback()) return false;
    int16_t pcm[320];
    int total = 16 * duration_ms;
    int produced = 0;
    size_t total_written = 0;
    ESP_LOGI(TAG, "tone start frequency=%d duration_ms=%d samples=%d", frequency, duration_ms, total);
    bool ok = true;
    while (produced < total) {
        int count = total - produced > 320 ? 320 : total - produced;
        for (int i = 0; i < count; ++i) {
            pcm[i] = (int16_t)(sin(2.0 * 3.141592653589793 * frequency * (produced + i) / 16000.0) * 9000.0);
        }
        size_t written = 0;
        esp_err_t err = i2s_channel_write(speaker, pcm, count * 2, &written, 1000);
        total_written += written;
        if (err != ESP_OK || written != count * 2) {
            ESP_LOGE(TAG, "tone write failed err=%s bytes=%u expected=%d", esp_err_to_name(err), (unsigned)written, count * 2);
            ok = false; break;
        }
        produced += count;
    }
    end_playback();
    ESP_LOGI(TAG, "tone complete ok=%d bytes=%u expected=%d", ok, (unsigned)total_written, total * 2);
    return ok;
}

static uint16_t read_u16(const uint8_t *p) { return p[0] | ((uint16_t)p[1] << 8); }
static uint32_t read_u32(const uint8_t *p) { return read_u16(p) | ((uint32_t)read_u16(p + 2) << 16); }

bool hanmir_speaker_play_url(const char *path)
{
    if (!speaker_enabled || !path || strncmp(path, "/tts/", 5) != 0 || strlen(path) > 160) return false;
    // Download short TTS completely before enabling I2S. Network stalls must
    // not drain the 60 ms DMA queue in the middle of a spoken sentence.
    const size_t capacity = 512 * 1024;
    int64_t started = esp_timer_get_time();
    uint8_t *wav = heap_caps_malloc(capacity, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!wav) {
        ESP_LOGE(TAG, "tts buffer allocation failed psram_free=%u heap_free=%u",
                 (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM),
                 (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT));
        return false;
    }
    char url[320];
    snprintf(url, sizeof(url), "http://%s:%d%s", CONFIG_HANMIR_SERVER_HOST, CONFIG_HANMIR_SERVER_PORT, path);
    esp_http_client_config_t config = {.url = url, .timeout_ms = 5000};
    esp_http_client_handle_t client = esp_http_client_init(&config);
    bool ok = client && esp_http_client_open(client, 0) == ESP_OK;
    int64_t expected = -1;
    if (ok) {
        expected = esp_http_client_fetch_headers(client);
        ok = esp_http_client_get_status_code(client) == 200 && expected >= 0 && expected <= (int64_t)capacity;
    }
    size_t used = 0;
    while (ok && used < capacity) {
        int n = esp_http_client_read(client, (char *)wav + used, capacity-used > 4096 ? 4096 : capacity-used);
        if (n < 0) { ok = false; break; }
        if (n == 0) break;
        used += n;
    }
    if (ok) ok = esp_http_client_is_complete_data_received(client) && (expected == 0 || used == (size_t)expected);
    if (client) esp_http_client_cleanup(client);
    int64_t download_us = esp_timer_get_time()-started;
    size_t pcm_offset=0, pcm_bytes=0;
    bool fmt_ok=false;
    if (ok) ok = used>=12 && !memcmp(wav,"RIFF",4) && !memcmp(wav+8,"WAVE",4)
                 && (uint64_t)read_u32(wav+4)+8 <= used;
    size_t riff_end = ok ? (size_t)read_u32(wav+4)+8 : 0;
    for (size_t offset=12; ok && offset+8<=riff_end;) {
        uint32_t length=read_u32(wav+offset+4);
        if (length > riff_end-offset-8) { ok=false; break; }
        const uint8_t *chunk=wav+offset+8;
        if (!memcmp(wav+offset,"fmt ",4)) {
            fmt_ok=length>=16 && read_u16(chunk)==1 && read_u16(chunk+2)==1 && read_u32(chunk+4)==16000
                   && read_u16(chunk+12)==2 && read_u16(chunk+14)==16;
        } else if (!memcmp(wav+offset,"data",4)) {
            pcm_offset=offset+8;pcm_bytes=length;
        }
        offset+=8+(size_t)length+(length&1);
    }
    ok = ok && fmt_ok && pcm_bytes>0 && !(pcm_bytes&1);
    ESP_LOGI(TAG, "tts preload ok=%d bytes=%u pcm=%u download_ms=%ld heap_free=%u psram_free=%u",
             ok,(unsigned)used,(unsigned)pcm_bytes,(long)(download_us/1000),
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
    size_t written_total=0;
    int64_t max_write_us=0, playback_started=esp_timer_get_time();
    if (ok) {
        ok=begin_playback();
        if (ok) {
            for (size_t offset=0;offset<pcm_bytes;) {
                size_t bytes=pcm_bytes-offset>2048?2048:pcm_bytes-offset,written=0;
                int64_t before=esp_timer_get_time();
                esp_err_t err=i2s_channel_write(speaker,wav+pcm_offset+offset,bytes,&written,1000);
                int64_t elapsed=esp_timer_get_time()-before;
                if (elapsed>max_write_us)max_write_us=elapsed;
                written_total+=written;
                if (err!=ESP_OK || written!=bytes) { ok=false;break; }
                offset+=bytes;
            }
            end_playback();
        }
    }
    heap_caps_free(wav);
    ESP_LOGI(TAG,"tts buffered complete ok=%d written=%u expected=%u playback_ms=%ld max_write_ms=%ld heap_free=%u psram_free=%u",
             ok,(unsigned)written_total,(unsigned)pcm_bytes,(long)((esp_timer_get_time()-playback_started)/1000),
             (long)(max_write_us/1000),(unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
    return ok;
}

// Fixed wake acknowledgement, PCM16 mono 16 kHz, generated once and embedded.
extern const uint8_t wake_ack_start[] asm("_binary_wake_ack_pcm_start");
extern const uint8_t wake_ack_end[] asm("_binary_wake_ack_pcm_end");
bool hanmir_speaker_ack(void)
{
    if (!speaker_enabled || !begin_playback()) return false;
    size_t length = wake_ack_end - wake_ack_start;
    bool ok = true;
    ESP_LOGI(TAG, "local acknowledgement start bytes=%u", (unsigned)length);
    for (size_t offset = 0; offset < length; offset += 640) {
        size_t count = length - offset > 640 ? 640 : length - offset;
        size_t written = 0;
        if (i2s_channel_write(speaker, wake_ack_start + offset, count, &written, 1000) != ESP_OK || written != count) {
            ok = false; break;
        }
    }
    end_playback();
    ESP_LOGI(TAG, "local acknowledgement complete ok=%d", ok);
    return ok;
}
