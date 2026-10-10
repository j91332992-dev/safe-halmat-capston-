#include "hanmir.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "hanmir_p4";

void app_main(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
    ESP_ERROR_CHECK(hanmir_pin_guard_validate());
    hanmir_sensors_init();
    ESP_ERROR_CHECK(hanmir_network_start());
    ESP_ERROR_CHECK(hanmir_camera_transport_start());
    err = hanmir_camera_source_start();
    if (err != ESP_OK) ESP_LOGW(TAG, "camera capture pending board validation: %s", esp_err_to_name(err));
    if (hanmir_speaker_start() == ESP_OK) {
        ESP_LOGI(TAG, "speaker I2S initialized");
    }
    ESP_ERROR_CHECK(hanmir_command_start());
    if (xTaskCreate(hanmir_api_task, "hanmir_api", 6144, NULL, 3, NULL) != pdPASS) {
        ESP_LOGE(TAG, "API task allocation failed");
    }
#if CONFIG_HANMIR_ENABLE_VOICE
    err = hanmir_voice_start();
    if (err != ESP_OK) ESP_LOGE(TAG, "voice not ready: %s", esp_err_to_name(err));
#endif
    err = hanmir_call_start();
    if (err != ESP_OK) ESP_LOGE(TAG, "call channel not ready: %s", esp_err_to_name(err));
}
