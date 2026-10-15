#pragma once
#include <stdint.h>
#include "uwb_diagnostics.h"

// Owned value data only; no pointer into the next ranging cycle or driver buffer.
struct AnchorSnapshot {
    bool received;
    int16_t legacy_cm;
    double raw_distance_m;
    uint64_t uptime_us, rx_dtu;
    uint32_t poll_tx_dtu, anchor_rx_dtu, anchor_tx_dtu, capture_us;
    int32_t ranging_clock_offset;
    uint8_t ipatov_rx_status;
    IpatovRaw diagnostic;
};
struct CycleSnapshot {
    uint64_t cycle_id, uptime_us;
    uint32_t dropped;
    uint8_t sequence, mask, beacon;
    AnchorSnapshot anchors[4];
};
