/*
  Makerfabs DW3000 multi-anchor/multi-tag tag example.
  Compatible with ESP32 + DW3000 and nRF52840 + DW3000 through dw3000_board_config.h.

For nRF52840+DW3000:
Additional boards manager URLs:https://adafruit.github.io/arduino-board-index/package_adafruit_index.json
Board: nrf52 V1.6.1

For ESP32+DW3000:
Board: esp32 2.0.16
*/
#include "dw3000.h"
#include <WiFi.h>
#include <HTTPClient.h>
#if __has_include("wifi_secrets.h")
#include "wifi_secrets.h"
#else
#define HANMIR_WIFI_SSID ""
#define HANMIR_WIFI_PASSWORD ""
#define HANMIR_SERVER_URL ""
#endif

#ifndef TAG_ID
#define TAG_ID              0
#endif
#ifndef UWB_WIFI_TELEMETRY
#define UWB_WIFI_TELEMETRY   1
#endif
#define NET_PAN_ID          0xDECA
#define MAX_ANCHORS         4
#define NUM_ANCHORS         4
#define MASTER_ANCHOR_ID    0xA0

#define FUNC_POLL           0xE0
#define FUNC_RESPONSE       0xE1
#define FUNC_REPORT         0xE2
#define FUNC_BEACON         0xE3

#ifndef TDMA_FRAME_MS
#define TDMA_FRAME_MS       300
#endif
#ifndef SLOT_DURATION_MS
#define SLOT_DURATION_MS    150
#endif
#define BEACON_GUARD_MS     20
#define BEACON_TIMEOUT_MS   900
static_assert(BEACON_GUARD_MS + (TAG_ID + 1) * SLOT_DURATION_MS <= TDMA_FRAME_MS, "Tag slot must fit TDMA frame");

const uint32_t anchor_delays[NUM_ANCHORS] = {
    2000, 7000, 12000, 17000
};

const uint8_t PIN_RST = DW3000_PIN_RST;
const uint8_t PIN_IRQ = DW3000_PIN_IRQ;
const uint8_t PIN_SS = DW3000_PIN_CS;

static dwt_config_t config = {
    5, DWT_PLEN_128, DWT_PAC8, 9, 9,
    1, DWT_BR_6M8, DWT_PHRMODE_STD, DWT_PHRRATE_STD,
    (129 + 8 - 8), DWT_STS_MODE_OFF, DWT_STS_LEN_64, DWT_PDOA_M0
};

#define TX_ANT_DLY 16385
#define RX_ANT_DLY 16385

static uint8_t tx_poll_msg[] = {
    0x41, 0x88, 0,
    0, 0, 0xFF, 0xFF, 0, 0,
    FUNC_POLL, 0, 0
};

static uint8_t tx_report_msg[] = {
    0x41, 0x88, 0,
    0, 0, 0xFF, 0xFF, 0, 0,
    FUNC_REPORT,
    0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
};

#define REPORT_MASK_IDX     10
#define REPORT_RANGE_IDX    11
#define BEACON_SEQ_IDX      10
#define BEACON_FRAME_IDX    11
#define BEACON_SLOT_IDX     13
#define RX_BUF_LEN          32

static uint8_t  rx_buffer[RX_BUF_LEN];
static int16_t  ranges_cm[MAX_ANCHORS];
static uint8_t  response_mask;
static uint8_t  responded_anchor_ids[MAX_ANCHORS];
static uint8_t  sequence_number = 0;
static uint32_t status_reg = 0;
static uint32_t synced_epoch_ms = 0;
static uint32_t last_beacon_ms = 0;
static uint8_t  last_beacon_sequence = 0;
static bool     is_time_synced = false;
static bool     is_slot_completed = false;
static uint32_t last_wifi_attempt_ms = 0;

#define WIFI_RETRY_INTERVAL_MS 10000

extern dwt_txconfig_t txconfig_options;

static void listen_for_beacon(uint16_t timeout_ms);
void perform_ranging(void);
static void handle_response_frame(uint32_t poll_tx_ts_32);
static void send_report(void);
static bool wifi_is_configured(void);
static void begin_wifi(void);

#include "uwb_telemetry.h"

static inline int get_anchor_index(uint16_t anchor_id)
{
    if (anchor_id >= 0xA0 && anchor_id < 0xA0 + NUM_ANCHORS)
    {
        return anchor_id - 0xA0;
    }

    return -1;
}

static inline uint16_t read_u16_le(const uint8_t *data)
{
    return (uint16_t)data[0] | ((uint16_t)data[1] << 8);
}


static inline void write_u16_le(uint8_t *data, uint16_t value)
{
    data[0] = (uint8_t)value;
    data[1] = (uint8_t)(value >> 8);
}

static bool wifi_is_configured()
{
    return UWB_WIFI_TELEMETRY && HANMIR_WIFI_SSID[0] != '\0' && HANMIR_SERVER_URL[0] != '\0';
}

static void begin_wifi()
{
    if (!wifi_is_configured())
    {
        Serial.println("[WIFI] disabled: run configure_wifi_tag.py");
        return;
    }

    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);
    WiFi.begin(HANMIR_WIFI_SSID, HANMIR_WIFI_PASSWORD);
    last_wifi_attempt_ms = millis();
    Serial.print("[WIFI] connecting to ");
    Serial.println(HANMIR_WIFI_SSID);
}

void setup()
{
    UART_init();
    // Four raw diagnostic records exceed 115200 baud at the nominal cycle rate.
    Serial.updateBaudRate(460800);

    tx_poll_msg[3] = (uint8_t)(NET_PAN_ID);
    tx_poll_msg[4] = (uint8_t)(NET_PAN_ID >> 8);
    tx_poll_msg[7] = (uint8_t)(TAG_ID);
    tx_poll_msg[8] = (uint8_t)(TAG_ID >> 8);

    tx_report_msg[3] = (uint8_t)(NET_PAN_ID);
    tx_report_msg[4] = (uint8_t)(NET_PAN_ID >> 8);
    tx_report_msg[7] = (uint8_t)(TAG_ID);
    tx_report_msg[8] = (uint8_t)(TAG_ID >> 8);

    spiBegin(PIN_IRQ, PIN_RST);
    spiSelect(PIN_SS);
    delay(2);

    dwt_softreset();
    delay(2);

    while (!dwt_checkidlerc())
    {
        test_run_info((unsigned char *)"IDLE FAILED\r\n");
        while (1);
    }

    if (dwt_initialise(DWT_DW_INIT) == DWT_ERROR)
    {
        test_run_info((unsigned char *)"INIT FAILED\r\n");
        while (1);
    }

    dwt_setleds(DWT_LEDS_ENABLE | DWT_LEDS_INIT_BLINK);

    if (dwt_configure(&config))
    {
        test_run_info((unsigned char *)"CONFIG FAILED\r\n");
        while (1);
    }

    dwt_configciadiag(DW_CIA_DIAG_LOG_ALL); // Single RX buffer, full Ipatov diagnostics.
    dwt_configuretxrf(&txconfig_options);
    dwt_setrxantennadelay(RX_ANT_DLY);
    dwt_settxantennadelay(TX_ANT_DLY);
    dwt_setlnapamode(DWT_LNA_ENABLE | DWT_PA_ENABLE);

    for (int i = 0; i < MAX_ANCHORS; i++)
    {
        ranges_cm[i] = 0;
        responded_anchor_ids[i] = 0xFF;
    }

    begin_wifi();
    start_telemetry();
}

// Receive A0 Beacon and synchronize the local TDMA epoch.
static void listen_for_beacon(uint16_t timeout_ms)
{
    dwt_setrxtimeout(timeout_ms * 1000UL);
    dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_CIADONE_BIT_MASK);
    dwt_rxenable(DWT_START_RX_IMMEDIATE);

    while (!((status_reg = dwt_read32bitreg(SYS_STATUS_ID)) &
             (SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_ALL_RX_TO | SYS_STATUS_ALL_RX_ERR)))
    {
    }

    if (status_reg & SYS_STATUS_RXFCG_BIT_MASK)
    {
        dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_RXFCG_BIT_MASK);

        uint32_t frame_len = dwt_read32bitreg(RX_FINFO_ID) & RXFLEN_MASK;
        uint16_t data_len = frame_len - FCS_LEN;

        if (data_len <= sizeof(rx_buffer) && data_len >= BEACON_SLOT_IDX + 2)
        {
            dwt_readrxdata(rx_buffer, data_len, 0);

            uint16_t rx_pan_id = read_u16_le(&rx_buffer[3]);
            uint16_t rx_src = read_u16_le(&rx_buffer[7]);
            uint8_t function_code = rx_buffer[9];

            if (rx_pan_id == NET_PAN_ID && rx_src == MASTER_ANCHOR_ID && function_code == FUNC_BEACON)
            {
                uint16_t beacon_frame_ms = read_u16_le(&rx_buffer[BEACON_FRAME_IDX]);
                uint16_t beacon_slot_ms = read_u16_le(&rx_buffer[BEACON_SLOT_IDX]);

                if (beacon_frame_ms == TDMA_FRAME_MS && beacon_slot_ms == SLOT_DURATION_MS)
                {
                    synced_epoch_ms = millis();
                    last_beacon_ms = synced_epoch_ms;
                    last_beacon_sequence = rx_buffer[BEACON_SEQ_IDX];
                    is_time_synced = true;
                    record_beacon_state(true);
                    is_slot_completed = false;
                }
            }
        }
    }
    else
    {
        dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_ALL_RX_TO | SYS_STATUS_ALL_RX_ERR);
    }
}

// Before synchronization, only listen for Beacon; after synchronization, use the Beacon epoch to divide TDMA slots.
void loop()
{
    if (!is_time_synced)
    {
        listen_for_beacon(200);
        return;
    }

    uint32_t now_ms = millis();

    if (now_ms - last_beacon_ms > BEACON_TIMEOUT_MS )
    {
        is_time_synced = false;
        record_beacon_state(false);
        is_slot_completed = false;
        return;
    }

    uint32_t elapsed_ms = millis() - synced_epoch_ms;
    uint32_t frame_offset_ms = elapsed_ms % TDMA_FRAME_MS;
    uint32_t slot_start_ms = BEACON_GUARD_MS + TAG_ID * SLOT_DURATION_MS;
    uint32_t slot_end_ms = slot_start_ms + SLOT_DURATION_MS;

    if (frame_offset_ms >= slot_start_ms && frame_offset_ms < slot_end_ms && !is_slot_completed)
    {
        perform_ranging();
        is_slot_completed = true;
    }

    if (frame_offset_ms < slot_start_ms || frame_offset_ms >= slot_end_ms)
    {
        is_slot_completed = false;

    }

    delay(1);
}

// Run one ranging cycle: send Poll, receive Anchor Responses, then send Report.
void perform_ranging()
{
    current_cycle = {};
    current_cycle.cycle_id = next_cycle++;
    current_cycle.sequence = sequence_number;
    current_cycle.uptime_us = esp_timer_get_time();
    current_cycle.beacon = last_beacon_sequence;
    for (int i = 0; i < MAX_ANCHORS; i++)
    {
        ranges_cm[i] = 0;
        responded_anchor_ids[i] = 0xFF;
    }

    response_mask = 0;

    dwt_setrxaftertxdelay(100);
    dwt_setrxtimeout(anchor_delays[0] + 2000);
    dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_ALL_RX_TO | SYS_STATUS_ALL_RX_ERR);

    dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_CIADONE_BIT_MASK);
    tx_poll_msg[2] = sequence_number;
    dwt_writetxdata(sizeof(tx_poll_msg), tx_poll_msg, 0);
    dwt_writetxfctrl(sizeof(tx_poll_msg), 0, 0);
    dwt_starttx(DWT_START_TX_IMMEDIATE | DWT_RESPONSE_EXPECTED);
    sequence_number++;

    while (!((status_reg = dwt_read32bitreg(SYS_STATUS_ID)) &
             (SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_ALL_RX_TO | SYS_STATUS_ALL_RX_ERR)))
    {
    }

    uint32_t poll_tx_ts_32 = dwt_readtxtimestamplo32();

    if (status_reg & SYS_STATUS_RXFCG_BIT_MASK)
    {
        handle_response_frame(poll_tx_ts_32);
    }

    dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_ALL_RX_TO | SYS_STATUS_ALL_RX_ERR);

    uint32_t previous_delay = anchor_delays[0];

    for (int i = 1; i < NUM_ANCHORS; i++)
    {
        uint32_t timeout = (anchor_delays[i] - previous_delay) + 2000;

        dwt_setrxtimeout(timeout);
        dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_CIADONE_BIT_MASK);
        dwt_rxenable(DWT_START_RX_IMMEDIATE);

        while (!((status_reg = dwt_read32bitreg(SYS_STATUS_ID)) &
                 (SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_ALL_RX_TO | SYS_STATUS_ALL_RX_ERR)))
        {
        }

        if (status_reg & SYS_STATUS_RXFCG_BIT_MASK)
        {
            handle_response_frame(poll_tx_ts_32);
        }
        else
        {
            dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_ALL_RX_TO | SYS_STATUS_ALL_RX_ERR);
        }

        previous_delay = anchor_delays[i];
    }

    send_report();
    current_cycle.mask = response_mask;
    enqueue_cycle(current_cycle);

}

// Handle a received Anchor Response frame.
static void handle_response_frame(uint32_t poll_tx_ts_32)
{
    const uint64_t received_us = esp_timer_get_time();
    const uint32_t capture_started_us = micros();
    const uint64_t rx_dtu = get_rx_timestamp_u64();
    uint32_t resp_rx_ts_32 = (uint32_t)rx_dtu;
    int32_t raw_clock_offset = dwt_readclockoffset();

    // Match P4 integration baseline 722c9fd: driver already sign-extends 13 bits.
    // Do not reintroduce the old main branch's incorrect bit-10 extension.
    float clock_offset = ((float)raw_clock_offset) / (uint32_t)(1 << 26);

    dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_CIADONE_BIT_MASK);

    uint32_t frame_len = dwt_read32bitreg(RX_FINFO_ID) & RXFLEN_MASK;
    uint16_t data_len = frame_len - FCS_LEN;

    if (data_len > sizeof(rx_buffer) || data_len < 18)
    {
        return;
    }

    dwt_readrxdata(rx_buffer, data_len, 0);

    if (rx_buffer[9] != FUNC_RESPONSE || rx_buffer[2] != current_cycle.sequence)
    {
        return;
    }

    if (read_u16_le(&rx_buffer[3]) != NET_PAN_ID || read_u16_le(&rx_buffer[5]) != TAG_ID)
    {
        return;
    }

    int anchor_idx = get_anchor_index(read_u16_le(&rx_buffer[7]));

    if (anchor_idx < 0)
    {
        return;
    }

    // No output/allocation here. Snapshot before re-enabling RX for next anchor.
    AnchorSnapshot &sample = current_cycle.anchors[anchor_idx];
    if (sample.received) return;
    sample.received = true;
    sample.uptime_us = received_us;
    sample.rx_dtu = rx_dtu;
    sample.poll_tx_dtu = poll_tx_ts_32;
    sample.ranging_clock_offset = raw_clock_offset;
    dwt_rxdiag_t diagnostic = {};
    dwt_readdiagnostics(&diagnostic);
    sample.diagnostic = {diagnostic.ipatovPower, diagnostic.ipatovF1, diagnostic.ipatovF2,
        diagnostic.ipatovF3, diagnostic.ipatovPeak, diagnostic.ipatovFpIndex,
        diagnostic.ipatovAccumCount, dwt_read32bitreg(0x30060),
        dwt_read32bitreg(DGC_CFG_ID), status_reg, (int16_t)raw_clock_offset,
        (status_reg & SYS_STATUS_CIADONE_BIT_MASK) != 0};
    sample.ipatov_rx_status = diagnostic.ipatovRxStatus;
    sample.capture_us = micros() - capture_started_us;

    uint32_t anchor_rx_ts;
    uint32_t anchor_tx_ts;
    resp_msg_get_ts(&rx_buffer[10], &anchor_rx_ts);
    resp_msg_get_ts(&rx_buffer[14], &anchor_tx_ts);

    uint32_t round_trip_time_32 = resp_rx_ts_32 - poll_tx_ts_32;
    uint32_t reply_delay_time_32 = anchor_tx_ts - anchor_rx_ts;
    double round_trip_time = (double)round_trip_time_32;
    double reply_delay_time = (double)reply_delay_time_32;

    if ((anchor_delays[anchor_idx] * 63898ULL) > 4294967295ULL)
    {
        round_trip_time += 4294967296.0;
        reply_delay_time += 4294967296.0;
    }

    double time_of_flight = ((round_trip_time - reply_delay_time * (1.0 - clock_offset)) / 2.0) * DWT_TIME_UNITS;
    sample.anchor_rx_dtu = anchor_rx_ts;
    sample.anchor_tx_dtu = anchor_tx_ts;
    sample.raw_distance_m = time_of_flight * SPEED_OF_LIGHT;
    int16_t distance_cm = (int16_t)(time_of_flight * SPEED_OF_LIGHT * 100 + 0.5);

    if (distance_cm < 0)
    {
        distance_cm = 0;
    }

    sample.legacy_cm = distance_cm;
    ranges_cm[anchor_idx] = distance_cm;
    responded_anchor_ids[anchor_idx] = (uint8_t)anchor_idx;
    response_mask |= (1 << anchor_idx);
}

// Broadcast 8 distance values.
static void send_report()
{
    tx_report_msg[REPORT_MASK_IDX] = response_mask;

    for (int i = 0; i < MAX_ANCHORS; i++)
    {
        write_u16_le(&tx_report_msg[REPORT_RANGE_IDX + i * 2], (uint16_t)ranges_cm[i]);
    }

    tx_report_msg[2] = tx_poll_msg[2];

    dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_TXFRS_BIT_MASK);
    dwt_writetxdata(sizeof(tx_report_msg), tx_report_msg, 0);
    dwt_writetxfctrl(sizeof(tx_report_msg), 0, 0);
    dwt_starttx(DWT_START_TX_IMMEDIATE);

    uint32_t report_tx_start_time = millis();

    while (!(dwt_read32bitreg(SYS_STATUS_ID) & SYS_STATUS_TXFRS_BIT_MASK))
    {
        if (millis() - report_tx_start_time > 50)
        {
            break;
        }
    }

    dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_TXFRS_BIT_MASK);
}
