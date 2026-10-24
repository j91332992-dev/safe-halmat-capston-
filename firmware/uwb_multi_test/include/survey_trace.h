#pragma once
#include <stdint.h>
#include <math.h>

// Version 1: saturating byte counters. A survey has <=100 slots, not a stream
// of per-packet log messages. No UART or additional RF inside a DS exchange.
enum SurveyStage : uint8_t {
    ST_SLOT_TX,ST_SLOT_RX,ST_ATTEMPT,ST_POLL_TX,ST_RESPONSE_RX,ST_RESPONSE_TX,
    ST_FINAL_TX,ST_FINAL_RX,ST_RESULT_TX,ST_RESULT_RX,ST_DISTANCE_OK,
    ST_RELAY_TX,ST_RELAY_RX,ST_RX_TIMEOUT,ST_RX_ERROR,ST_FRAME_MISMATCH,
    ST_TX_ERROR,ST_CIA_ERROR,ST_TX_TIMESTAMP_ERROR,ST_INTERVAL_ERROR,
    ST_DISTANCE_ERROR,ST_RELAY_ERROR,ST_UNEXPECTED_RX,ST_SS_ATTEMPT,
    ST_COUNT
};
static constexpr const char *SURVEY_STAGE_NAMES[ST_COUNT]={
    "slot_tx","slot_rx","attempt","poll_tx","response_rx","response_tx",
    "final_tx","final_rx","result_tx","result_rx","distance_ok",
    "relay_tx","relay_rx","rx_timeout","rx_error","frame_mismatch",
    "tx_error","cia_error","tx_timestamp_error","interval_error",
    "distance_error","relay_error","unexpected_rx","ss_attempt"
};
struct SurveyTrace {
    uint8_t anchor,a,b,counts[ST_COUNT];
    bool received;
    uint32_t last_status;
    uint8_t last_function;
    float last_distance;
};
static inline void survey_trace_increment(SurveyTrace &trace,SurveyStage stage){
    if(trace.counts[stage]<255)++trace.counts[stage];
}
