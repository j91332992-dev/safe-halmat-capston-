#pragma once

#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define SERVER_BASE_URL "http://192.168.0.10:8000"

#define ORGANIZATION_ID "org-001"
#define SITE_ID "site-001"
#define WORKER_ID "worker-001"
#define HELMET_ID "helmet-001"
#define DEVICE_ID "helmet-001-uwb"
#define UWB_TAG_ID "tag-001"

// 1차 버전 기본값. 실제 DW3000 라이브러리 확정 후 false로 바꾼다.
#define UWB_USE_MOCK true
#define UWB_SPI_SCK 18
#define UWB_SPI_MISO 19
#define UWB_SPI_MOSI 23
#define UWB_SPI_CS 4
#define UWB_IRQ 34
#define UWB_RST 27
#define BATTERY_ADC_PIN 35
#define SEND_INTERVAL_MS 500
#define HEARTBEAT_INTERVAL_MS 5000

