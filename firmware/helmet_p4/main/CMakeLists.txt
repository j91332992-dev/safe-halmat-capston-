idf_component_register(
    SRCS "app_main.c" "network.c" "api_client.c" "camera_transport.c" "camera_source.c" "voice.c" "sensors.c" "speaker.c" "command_client.c" "pin_guard.c"
    INCLUDE_DIRS "."
    REQUIRES esp_wifi esp_netif esp_event nvs_flash esp_http_client json
             esp_websocket_client driver esp_timer esp_video esp_driver_jpeg
)
