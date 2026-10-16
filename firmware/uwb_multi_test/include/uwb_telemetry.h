#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <esp_timer.h>
#include <Preferences.h>
#include "uwb_diagnostics.h"
#include "uwb_delivery_policy.h"
#include "uwb_measurement_snapshot.h"

static const char *capture_firmware_version = "uwb-capture-20261015.2";
static const char *capture_source_revision = "722c9fd+uwb-log-20261015.2";

static LatestQueue<CycleSnapshot, UWB_USB_QUEUE_CAPACITY> usb_queue;
static LatestQueue<CycleSnapshot, UWB_HTTP_QUEUE_CAPACITY> http_queue;
static portMUX_TYPE telemetry_mux = portMUX_INITIALIZER_UNLOCKED;
struct DeliveryStats {
    uint32_t measured, usb_overflow, http_overflow, superseded, expired, offline;
    uint32_t attempts, succeeded, failed, retried, terminal, late_completed;
    uint32_t beacon_acquired, beacon_lost;
    uint64_t last_measured_us, interval_us, max_interval_us, ranging_us;
    uint64_t last_http_cycle, http_duration_us, http_age_us;
    int last_http_status;
    bool beacon_synced;
};
static DeliveryStats delivery_stats = {};
static char telemetry_session[100];
static CycleSnapshot current_cycle;
static uint64_t next_cycle = 0;

// Only the ranging owner calls these functions. Both queues hold value copies.
static void enqueue_cycle(CycleSnapshot &cycle) {
    const uint64_t completed_us = esp_timer_get_time();
    portENTER_CRITICAL(&telemetry_mux);
    if (delivery_stats.last_measured_us) {
        delivery_stats.interval_us = cycle.uptime_us - delivery_stats.last_measured_us;
        if (delivery_stats.interval_us > delivery_stats.max_interval_us)
            delivery_stats.max_interval_us = delivery_stats.interval_us;
    }
    delivery_stats.last_measured_us = cycle.uptime_us;
    delivery_stats.ranging_us = completed_us - cycle.uptime_us;
    ++delivery_stats.measured;
    cycle.dropped = delivery_stats.usb_overflow;
    if (usb_queue.push(cycle)) ++delivery_stats.usb_overflow;
    if (wifi_is_configured() && http_queue.push(cycle)) ++delivery_stats.http_overflow;
    portEXIT_CRITICAL(&telemetry_mux);
}
static void record_beacon_state(bool synced) {
    portENTER_CRITICAL(&telemetry_mux);
    delivery_stats.beacon_synced = synced;
    if (synced) ++delivery_stats.beacon_acquired;
    else ++delivery_stats.beacon_lost;
    portEXIT_CRITICAL(&telemetry_mux);
}

inline String uint64_string(uint64_t value) {
    char buffer[24]; snprintf(buffer, sizeof(buffer), "%llu", (unsigned long long)value);
    return String(buffer);
}
inline String json_number(double value, unsigned decimals = 6) {
    return isfinite(value) ? String(value, decimals) : String("null");
}

// Runs only on the telemetry task, after the complete ranging/report exchange.
static String serialize_cycle(const CycleSnapshot &cycle) {
    String id = String(telemetry_session) + ":" + uint64_string(cycle.cycle_id);
    String payload; payload.reserve(7000);
    payload = "{\"schema_version\":2,\"organization_id\":\"org-001\",\"site_id\":\"site-001\","
              "\"worker_id\":\"worker-001\",\"helmet_id\":\"helmet-001\",\"device_id\":\"helmet-001-uwb\","
              "\"distances_calibrated\":false,\"time_basis\":\"device_monotonic_us\",\"measured_at\":null,";
    payload += "\"uwb_tag_id\":\"tag-";
    char tag[8]; snprintf(tag, sizeof(tag), "%03u", TAG_ID + 1); payload += tag;
    payload += "\",\"tag_hw_id\":" + String(TAG_ID);
    payload += ",\"firmware_version\":\"" + String(capture_firmware_version) + "\"";
    payload += ",\"source_revision\":\"" + String(capture_source_revision) + "\"";
    payload += ",\"session_id\":\"" + String(telemetry_session) + "\",\"measurement_id\":\"" + id + "\"";
    payload += ",\"cycle_id\":" + uint64_string(cycle.cycle_id) + ",\"sequence\":" + String(cycle.sequence);
    payload += ",\"measured_uptime_us\":" + uint64_string(cycle.uptime_us);
    payload += ",\"firmware_dropped_cycles\":" + String(cycle.dropped);
    payload += ",\"observations\":[";
    String measurements;
    bool first_measurement = true;
    for (unsigned i = 0; i < 4; ++i) {
        const AnchorSnapshot &anchor = cycle.anchors[i];
        const IpatovRaw &raw = anchor.diagnostic;
        const IpatovResult calc = calculate_ipatov(raw, config.rxCode, config.chan);
        String diagnostic = "{\"direction\":\"anchor_to_tag\",\"sequence\":\"ipatov\",\"status\":\"";
        diagnostic += !anchor.received ? "missing" : calc.reason ? "invalid" : "valid";
        diagnostic += "\",\"reason\":";
        if (!anchor.received) diagnostic += "\"no_response\"";
        else if (calc.reason) diagnostic += String("\"") + calc.reason + "\"";
        else diagnostic += "null";
        diagnostic += ",\"rx_power_dbm\":" + json_number(calc.rx_dbm);
        diagnostic += ",\"first_path_power_dbm\":" + json_number(calc.fp_dbm);
        diagnostic += ",\"power_difference_db\":" + json_number(calc.difference_db);
        diagnostic += ",\"peak_minus_first_path_samples\":" + json_number(calc.peak_minus_fp_samples);
        diagnostic += ",\"clock_offset_ppm\":" + (anchor.received ? json_number(calc.clock_ppm) : String("null"));
        diagnostic += ",\"raw\":{";
        if (anchor.received) {
            diagnostic += "\"ipatov_power\":" + String(raw.power) + ",\"ipatov_f1\":" + String(raw.f1);
            diagnostic += ",\"ipatov_f2\":" + String(raw.f2) + ",\"ipatov_f3\":" + String(raw.f3);
            diagnostic += ",\"ipatov_peak\":" + String(raw.peak) + ",\"ipatov_fp_index\":" + String(raw.fp_index);
            diagnostic += ",\"ipatov_accum_count\":" + String(raw.accum_count);
            diagnostic += ",\"dgc_debug\":" + String(raw.dgc_debug) + ",\"dgc_config\":" + String(raw.dgc_config);
            diagnostic += ",\"clock_offset\":" + String(raw.clock_offset) + ",\"sys_status\":" + String(raw.rx_status);
            diagnostic += ",\"ranging_clock_offset\":" + String(anchor.ranging_clock_offset);
            diagnostic += ",\"cia_done\":" + String(raw.cia_done ? "true" : "false");
            diagnostic += ",\"ipatov_rx_status\":" + String(anchor.ipatov_rx_status);
            diagnostic += ",\"capture_us\":" + String(anchor.capture_us);
            diagnostic += ",\"poll_tx_dtu_low32\":" + String(anchor.poll_tx_dtu);
            diagnostic += ",\"anchor_poll_rx_dtu_low32\":" + String(anchor.anchor_rx_dtu);
            diagnostic += ",\"anchor_response_tx_dtu_low32\":" + String(anchor.anchor_tx_dtu);
            diagnostic += ",\"channel\":" + String(config.chan) + ",\"rx_code\":" + String(config.rxCode);
            diagnostic += ",\"sts_mode\":" + String(config.stsMode);
        }
        diagnostic += "}}";
        String anchor_id = String("anchor-00") + String(i + 1);
        if (i) payload += ',';
        payload += "{\"anchor_id\":\"" + anchor_id + "\",\"anchor_hw_id\":" + String(0xa0 + i);
        payload += ",\"status\":\"" + String(!anchor.received ? "missing" :
                    (isfinite(anchor.raw_distance_m) && anchor.raw_distance_m > 0 && anchor.legacy_cm > 0) ? "valid" : "invalid") + "\"";
        payload += ",\"raw_distance_m\":" + (anchor.received ? json_number(anchor.raw_distance_m) : String("null"));
        payload += ",\"legacy_range_cm\":" + (anchor.received ? String(anchor.legacy_cm) : String("null"));
        payload += ",\"measured_uptime_us\":" + (anchor.received ? uint64_string(anchor.uptime_us) : String("null"));
        payload += ",\"rx_timestamp_dtu\":" + (anchor.received ? uint64_string(anchor.rx_dtu) : String("null"));
        payload += ",\"diagnostics\":" + diagnostic + "}";
        if (anchor.received && anchor.legacy_cm > 0) {
            if (!first_measurement) measurements += ',';
            first_measurement = false;
            measurements += "{\"anchor_id\":\"" + anchor_id + "\",\"distance_m\":" + String(anchor.legacy_cm / 100.0, 2);
            // Retain the old Wi-Fi solver weight; this is NOT a UWB quality score.
            measurements += ",\"quality\":0.95,\"raw_distance_m\":" + json_number(anchor.raw_distance_m);
            measurements += ",\"source_measurement_id\":\"" + id + "\"}";
        }
    }
    payload += "],\"measurements\":[" + measurements + "]}";
    return payload;
}

// This is the only telemetry Serial writer. HTTP never delays USB output.
static void usb_telemetry_task(void *) {
    CycleSnapshot snapshot;
    uint32_t last_stats_ms = millis();
    for (;;) {
        portENTER_CRITICAL(&telemetry_mux);
        bool available = usb_queue.pop(snapshot);
        portEXIT_CRITICAL(&telemetry_mux);
        if (available) Serial.println(serialize_cycle(snapshot));
        if (millis() - last_stats_ms >= 5000) {
            DeliveryStats s;
            size_t usb_depth, http_depth;
            portENTER_CRITICAL(&telemetry_mux);
            s = delivery_stats; usb_depth = usb_queue.size(); http_depth = http_queue.size();
            portEXIT_CRITICAL(&telemetry_mux);
            Serial.printf("[UWB_DELIVERY] session=%s measured=%lu usb_q=%u http_q=%u usb_drop=%lu http_drop=%lu superseded=%lu expired=%lu offline=%lu attempts=%lu ok=%lu failed=%lu retried=%lu terminal=%lu late=%lu http_status=%d http_cycle=%llu http_duration_us=%llu http_age_us=%llu interval_us=%llu max_interval_us=%llu ranging_us=%llu synced=%u beacon_acquired=%lu beacon_lost=%lu\n",
                telemetry_session, (unsigned long)s.measured, (unsigned)usb_depth, (unsigned)http_depth,
                (unsigned long)s.usb_overflow, (unsigned long)s.http_overflow,
                (unsigned long)s.superseded, (unsigned long)s.expired, (unsigned long)s.offline,
                (unsigned long)s.attempts, (unsigned long)s.succeeded, (unsigned long)s.failed,
                (unsigned long)s.retried, (unsigned long)s.terminal, (unsigned long)s.late_completed,
                s.last_http_status, (unsigned long long)s.last_http_cycle,
                (unsigned long long)s.http_duration_us, (unsigned long long)s.http_age_us,
                (unsigned long long)s.interval_us, (unsigned long long)s.max_interval_us,
                (unsigned long long)s.ranging_us, s.beacon_synced,
                (unsigned long)s.beacon_acquired, (unsigned long)s.beacon_lost);
            last_stats_ms = millis();
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

static void http_telemetry_task(void *) {
    CycleSnapshot snapshot;
    uint32_t last_wifi_attempt = millis();
    for (;;) {
        portENTER_CRITICAL(&telemetry_mux);
        bool available = http_queue.pop_latest(snapshot, delivery_stats.superseded);
        portEXIT_CRITICAL(&telemetry_mux);
        if (!available) { vTaskDelay(pdMS_TO_TICKS(20)); continue; }
        if (WiFi.status() != WL_CONNECTED) {
            if (millis() - last_wifi_attempt >= WIFI_RETRY_INTERVAL_MS) {
                WiFi.disconnect(); WiFi.begin(HANMIR_WIFI_SSID, HANMIR_WIFI_PASSWORD);
                last_wifi_attempt = millis();
            }
            portENTER_CRITICAL(&telemetry_mux);
            ++delivery_stats.offline;
            portEXIT_CRITICAL(&telemetry_mux);
            continue;
        }
        // Construct once, retain exactly these bytes/ID/Poll time on retries.
        String payload = serialize_cycle(snapshot);
        payload.remove(payload.length() - 1); payload += ",\"transport\":\"wifi\"}";
        unsigned attempts = 0;
        for (;;) {
            if (delivery_expired(snapshot.uptime_us, esp_timer_get_time())) {
                portENTER_CRITICAL(&telemetry_mux);
                ++delivery_stats.expired;
                portEXIT_CRITICAL(&telemetry_mux);
                break;
            }
            WiFiClient client; HTTPClient http;
            const uint64_t started_us = esp_timer_get_time();
            http.setConnectTimeout(UWB_HTTP_CONNECT_TIMEOUT_MS);
            http.setTimeout(UWB_HTTP_READ_TIMEOUT_MS);
            int code = -1;
            if (http.begin(client, HANMIR_SERVER_URL)) {
                http.addHeader("Content-Type", "application/json");
                code = http.POST(payload);
            }
            http.end();
            const uint64_t completed_us = esp_timer_get_time();
            ++attempts;
            const bool success = code >= 200 && code < 300;
            portENTER_CRITICAL(&telemetry_mux);
            ++delivery_stats.attempts;
            if (attempts > 1) ++delivery_stats.retried;
            delivery_stats.last_http_status = code;
            delivery_stats.last_http_cycle = snapshot.cycle_id;
            delivery_stats.http_duration_us = completed_us - started_us;
            delivery_stats.http_age_us = completed_us - snapshot.uptime_us;
            if (success) ++delivery_stats.succeeded; else ++delivery_stats.failed;
            if (delivery_expired(snapshot.uptime_us, esp_timer_get_time())) ++delivery_stats.late_completed;
            portEXIT_CRITICAL(&telemetry_mux);
            if (success) break;
            if (!delivery_retryable(code, attempts)) {
                portENTER_CRITICAL(&telemetry_mux);
                ++delivery_stats.terminal;
                portEXIT_CRITICAL(&telemetry_mux);
                break;
            }
            vTaskDelay(pdMS_TO_TICKS(UWB_HTTP_RETRY_MS));
            // A new cycle has priority over retrying an older measurement.
            portENTER_CRITICAL(&telemetry_mux);
            bool newer = http_queue.size() > 0;
            if (newer) ++delivery_stats.superseded;
            portEXIT_CRITICAL(&telemetry_mux);
            if (newer) break;
        }
    }
}

static void start_telemetry() {
    Preferences prefs;
    uint64_t boot = 0;
    if (prefs.begin("uwb_capture", false)) {
        boot = prefs.getULong64("boot", 0) + 1;
        if (!prefs.putULong64("boot", boot)) boot = 0;
        prefs.end();
    }
    // MAC + persistent boot count + random nonce even if NVS is erased/unavailable.
    snprintf(telemetry_session, sizeof(telemetry_session), "%012llx-%llu-%08lx%08lx%08lx%08lx",
             (unsigned long long)ESP.getEfuseMac(), (unsigned long long)boot,
             (unsigned long)esp_random(), (unsigned long)esp_random(),
             (unsigned long)esp_random(), (unsigned long)esp_random());
    Serial.printf("[UWB_CAPTURE] firmware=%s source=%s tag=%u mode=%s baud=460800 session=%s\n",
                  capture_firmware_version, capture_source_revision, TAG_ID,
                  wifi_is_configured() ? "wifi+usb" : "usb_only", telemetry_session);
    if (xTaskCreatePinnedToCore(usb_telemetry_task, "uwb-usb", 12288, nullptr, 1, nullptr, 0) != pdPASS ||
        (wifi_is_configured() && xTaskCreatePinnedToCore(http_telemetry_task, "uwb-http", 12288, nullptr, 1, nullptr, 0) != pdPASS)) {
        Serial.println("[UWB_LOG] task/queue allocation failed");
        while (true) delay(1000);
    }
}
