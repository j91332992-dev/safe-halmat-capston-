#pragma once
#include <WiFi.h>

#ifndef HANMIR_WIFI_SSID_2
#define HANMIR_WIFI_SSID_2 ""
#endif
#ifndef HANMIR_WIFI_PASSWORD_2
#define HANMIR_WIFI_PASSWORD_2 ""
#endif

// Called by the network owner only; no scans or waits on the UWB radio loop.
static unsigned hanmir_wifi_profile = 0;
static uint32_t hanmir_wifi_attempt_at = 0;
static const char *const hanmir_wifi_ssids[] = {HANMIR_WIFI_SSID, HANMIR_WIFI_SSID_2};
static const char *const hanmir_wifi_passwords[] = {HANMIR_WIFI_PASSWORD, HANMIR_WIFI_PASSWORD_2};
static void hanmir_wifi_connect_profile(unsigned profile) {
    hanmir_wifi_profile = profile;
    WiFi.disconnect(false, false);
    WiFi.begin(hanmir_wifi_ssids[profile], hanmir_wifi_passwords[profile]);
    hanmir_wifi_attempt_at = millis();
    Serial.printf("[WIFI] profile=%u SSID=%s\n", profile + 1, hanmir_wifi_ssids[profile]);
}
static void hanmir_wifi_begin() {
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);
    WiFi.setAutoReconnect(false);
    hanmir_wifi_connect_profile(0);
}
static void hanmir_wifi_maintain() {
    if (WiFi.status() == WL_CONNECTED) {
        hanmir_wifi_attempt_at = millis();
        return;
    }
    if ((uint32_t)(millis() - hanmir_wifi_attempt_at) >= 10000) {
        unsigned next = hanmir_wifi_ssids[1][0] ? 1 - hanmir_wifi_profile : 0;
        hanmir_wifi_connect_profile(next);
    }
}
