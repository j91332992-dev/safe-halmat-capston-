#pragma once
#include <WebSocketsClient.h>

// Four ACK slots bound memory and outstanding work. Old ranges are never replayed.
static void ws_telemetry_task(void *) {
    WebSocketsClient ws;
    struct Pending { bool used; uint64_t id, sent, measured; } pending[4] = {};
    bool connected = false;
    String url = HANMIR_SERVER_URL;
    int scheme = url.indexOf("://");
    String authority = url.substring(scheme + 3);
    int slash = authority.indexOf('/');
    if (slash >= 0) authority = authority.substring(0, slash);
    int colon = authority.indexOf(':');
    String host = colon >= 0 ? authority.substring(0, colon) : authority;
    uint16_t port = colon >= 0 ? authority.substring(colon + 1).toInt() : 80;
    ws.onEvent([&](WStype_t type, uint8_t *data, size_t length) {
        if (type == WStype_CONNECTED) connected = true;
        else if (type == WStype_DISCONNECTED) {
            connected = false;
            portENTER_CRITICAL(&telemetry_mux);
            for (auto &p : pending) { if (p.used) ++delivery_stats.failed; p.used = false; }
            portEXIT_CRITICAL(&telemetry_mux);
        } else if (type == WStype_TEXT && length < 80) {
            char ack[80]; memcpy(ack, data, length); ack[length] = 0;
            unsigned long long id; int code;
            if (sscanf(ack, "ack:%llu:%d", &id, &code) != 2) return;
            for (auto &p : pending) if (p.used && p.id == id) {
                uint64_t now = esp_timer_get_time();
                portENTER_CRITICAL(&telemetry_mux);
                delivery_stats.last_http_status = code;
                delivery_stats.last_http_cycle = id;
                delivery_stats.http_duration_us = now - p.sent;
                delivery_stats.http_age_us = now - p.measured;
                if (code >= 200 && code < 300) ++delivery_stats.succeeded;
                else { ++delivery_stats.failed; delivery_stats.last_http_error = code; }
                portEXIT_CRITICAL(&telemetry_mux);
                p.used = false; break;
            }
        }
    });
    ws.begin(host, port, "/api/uwb/stream", "");
    ws.setReconnectInterval(1000);
    for (;;) {
        hanmir_wifi_maintain();
        ws.loop();
        uint64_t now = esp_timer_get_time();
        bool stale = false;
        for (auto &p : pending) if (p.used && now-p.sent > 1000000) stale = true;
        if (stale) { ws.disconnect(); connected = false; }
        Pending *slot = nullptr;
        for (auto &p : pending) if (!p.used) { slot = &p; break; }
        if (connected && slot) {
            CycleSnapshot snapshot;
            portENTER_CRITICAL(&telemetry_mux);
            bool available = http_queue.pop_latest(snapshot, delivery_stats.superseded);
            portEXIT_CRITICAL(&telemetry_mux);
            if (available) {
                if (delivery_expired(snapshot.uptime_us, now)) {
                    portENTER_CRITICAL(&telemetry_mux); ++delivery_stats.expired; portEXIT_CRITICAL(&telemetry_mux);
                } else {
                    String payload = serialize_cycle(snapshot);
                    payload.remove(payload.length()-1); payload += ",\"transport\":\"wifi-ws\"}";
                    *slot = {true, snapshot.cycle_id, (uint64_t)esp_timer_get_time(), snapshot.uptime_us};
                    bool sent = ws.sendTXT(payload);
                    portENTER_CRITICAL(&telemetry_mux);
                    ++delivery_stats.attempts;
                    if (!sent) { ++delivery_stats.failed; delivery_stats.last_http_error = -100; }
                    portEXIT_CRITICAL(&telemetry_mux);
                    if (!sent) { slot->used = false; ws.disconnect(); connected = false; }
                }
            }
        }
        vTaskDelay(pdMS_TO_TICKS(2));
    }
}
