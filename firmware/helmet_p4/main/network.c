#include <string.h>
#include "hanmir.h"
#include "esp_event.h"
#include "esp_check.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "hanmir_wifi";
static volatile bool online;

static void wifi_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        online = false;
        ESP_LOGW(TAG, "Wi-Fi lost; reconnecting");
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        online = true;
        ip_event_got_ip_t *event = data;
        ESP_LOGI(TAG, "IP=" IPSTR, IP2STR(&event->ip_info.ip));
    }
}

static void resource_monitor(void *arg)
{
    for (;;) {
        ESP_LOGI(TAG, "resources heap_free=%u heap_min=%u heap_largest=%u psram_free=%u psram_min=%u rssi=%d",
            (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
            (unsigned)heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
            (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
            (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM),
            (unsigned)heap_caps_get_minimum_free_size(MALLOC_CAP_SPIRAM), hanmir_network_rssi());
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

esp_err_t hanmir_network_start(void)
{
    if (!CONFIG_HANMIR_WIFI_SSID[0]) {
        ESP_LOGE(TAG, "Set Wi-Fi SSID in menuconfig");
        return ESP_ERR_INVALID_ARG;
    }
    ESP_RETURN_ON_ERROR(esp_netif_init(), TAG, "netif init");
    ESP_RETURN_ON_ERROR(esp_event_loop_create_default(), TAG, "event loop");
    esp_netif_create_default_wifi_sta();
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_RETURN_ON_ERROR(esp_wifi_init(&init), TAG, "Wi-Fi init / C6 hosted transport");
    ESP_RETURN_ON_ERROR(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_event, NULL), TAG, "Wi-Fi events");
    ESP_RETURN_ON_ERROR(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, wifi_event, NULL), TAG, "IP events");
    wifi_config_t config = {0};
    strlcpy((char *)config.sta.ssid, CONFIG_HANMIR_WIFI_SSID, sizeof(config.sta.ssid));
    strlcpy((char *)config.sta.password, CONFIG_HANMIR_WIFI_PASSWORD, sizeof(config.sta.password));
    ESP_RETURN_ON_ERROR(esp_wifi_set_mode(WIFI_MODE_STA), TAG, "STA mode");
    ESP_RETURN_ON_ERROR(esp_wifi_set_config(WIFI_IF_STA, &config), TAG, "STA config");
    ESP_RETURN_ON_ERROR(esp_wifi_start(), TAG, "Wi-Fi start");
    wifi_ps_type_t previous = WIFI_PS_NONE;
    esp_err_t query = esp_wifi_get_ps(&previous);
    esp_err_t ps = esp_wifi_set_ps(WIFI_PS_NONE);
    ESP_LOGI(TAG, "Wi-Fi latency mode previous_ps=%d query=%s set_none=%s",
             previous, esp_err_to_name(query), esp_err_to_name(ps));
    if (xTaskCreate(resource_monitor, "resource_log", 4096, NULL, 1, NULL) != pdPASS)
        ESP_LOGW(TAG, "resource monitor unavailable");
    return ESP_OK;
}

bool hanmir_network_online(void) { return online; }

int hanmir_network_rssi(void)
{
    wifi_ap_record_t ap = {0};
    return online && esp_wifi_sta_get_ap_info(&ap) == ESP_OK ? ap.rssi : 0;
}
