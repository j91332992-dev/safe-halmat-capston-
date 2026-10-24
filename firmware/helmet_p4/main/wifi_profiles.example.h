#pragma once
// Optional local SSID correction without changing every component's sdkconfig.h.
// Copy to wifi_profiles.local.h (gitignored). Passwords still come from menuconfig.
// Remove the local file to use CONFIG_HANMIR_WIFI_SSID directly.
#define HANMIR_WIFI_PRIMARY_SSID "YOUR_2_4_GHZ_WIFI"
