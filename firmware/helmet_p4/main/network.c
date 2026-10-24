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
#if __has_include("wifi_profiles.local.h")
#include "wifi_profiles.local.h"
#endif
#ifndef HANMIR_WIFI_PRIMARY_SSID
#define HANMIR_WIFI_PRIMARY_SSID CONFIG_HANMIR_WIFI_SSID
#endif

static const char *TAG = "hanmir_wifi";
static volatile bool online;
static unsigned wifi_profile;
static unsigned wifi_failures;
static const char *wifi_ssids[] = {HANMIR_WIFI_PRIMARY_SSID, CONFIG_HANMIR_WIFI_SSID_2};
static const char *wifi_passwords[] = {CONFIG_HANMIR_WIFI_PASSWORD, CONFIG_HANMIR_WIFI_PASSWORD_2};

static esp_err_t select_wifi_profile(unsigned profile)
{
    wifi_config_t config = {0};
    strlcpy((char *)config.sta.ssid, wifi_ssids[profile], sizeof(config.sta.ssid));
    strlcpy((char *)config.sta.password, wifi_passwords[profile], sizeof(config.sta.password));
    esp_err_t err = esp_wifi_set_config(WIFI_IF_STA, &config);
    if (err == ESP_OK) {
        wifi_profile = profile;
        ESP_LOGI(TAG, "Wi-Fi profile=%u SSID=%s", profile + 1, wifi_ssids[profile]);
    }
    return err;
}

static void wifi_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        online = false;
        wifi_event_sta_disconnected_t *event = data;
        ESP_LOGW(TAG, "Wi-Fi disconnected profile=%u reason=%u failures=%u",
                 wifi_profile + 1, event ? event->reason : 0, wifi_failures + 1);
        if (++wifi_failures >= 2 && wifi_ssids[1][0]) {
            esp_err_t err = select_wifi_profile(1 - wifi_profile);
            if (err != ESP_OK) ESP_LOGW(TAG, "Wi-Fi switch failed: %s", esp_err_to_name(err));
            wifi_failures = 0;
        }
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        online = true;
        wifi_failures = 0;
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
    if (!wifi_ssids[0][0]) {
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
    ESP_RETURN_ON_ERROR(esp_wifi_set_mode(WIFI_MODE_STA), TAG, "STA mode");
    ESP_RETURN_ON_ERROR(esp_wifi_set_storage(WIFI_STORAGE_RAM), TAG, "Wi-Fi RAM config");
    ESP_RETURN_ON_ERROR(select_wifi_profile(0), TAG, "STA config");
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
