#pragma once

// configure_wifi_tag.py가 실제 wifi_secrets.h를 생성합니다.
#define HANMIR_WIFI_SSID "YOUR_2_4_GHZ_WIFI"
#define HANMIR_WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define HANMIR_WIFI_SSID_2 "YOUR_SECOND_2_4_GHZ_WIFI"
#define HANMIR_WIFI_PASSWORD_2 "YOUR_SECOND_WIFI_PASSWORD"
#define HANMIR_SERVER_URL "http://192.168.0.10:8000/api/uwb/distances"
// Provision locally with tools/provision_anchor_survey.py for anchor-01-survey.
// Never commit the real shared device key.
#define HANMIR_SURVEY_TOKEN ""
