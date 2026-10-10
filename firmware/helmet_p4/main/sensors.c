#include "hanmir.h"
#include "driver/i2c_master.h"
#include "driver/uart.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "esp_rom_sys.h"
#include <math.h>
#include <inttypes.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "bno_sh2/sh2.h"
#include "bno_sh2/sh2_err.h"
#include "bno_sh2/sh2_SensorValue.h"

static const char *TAG = "hanmir_sensors";
static i2c_master_dev_handle_t fuel_gauge;
static sh2_Hal_t imu_hal;
static portMUX_TYPE imu_mux = portMUX_INITIALIZER_UNLOCKED;
static float imu_yaw, imu_pitch, imu_roll;
static int64_t imu_report_us;
static bool imu_reset_seen;

#define IMU_UART UART_NUM_1
#define IMU_UART_BAUD 3000000
#define IMU_REPORT_INTERVAL_US 100000
#define IMU_RX_TIMEOUT_MS 5
#define SHTP_UART_MARKER 0x7E
#define SHTP_UART_ESCAPE 0x7D

static int imu_hal_wait_for_data(void)
{
    // SH-2 configuration calls synchronously poll this HAL while waiting for
    // acknowledgements. Yield here so that polling cannot starve IDLE/WDT.
    vTaskDelay(1);
    return 0;
}

static int uart_frame_write(const uint8_t *packet, size_t length)
{
    uint8_t framed[SH2_HAL_MAX_TRANSFER_OUT * 2 + 4];
    size_t used = 0;
    framed[used++] = SHTP_UART_MARKER;
    framed[used++] = 0x01;
    for (size_t i = 0; i < length; ++i) {
        if (packet[i] == SHTP_UART_MARKER || packet[i] == SHTP_UART_ESCAPE) {
            if (used + 2 >= sizeof(framed)) return -1;
            framed[used++] = SHTP_UART_ESCAPE;
            framed[used++] = packet[i] ^ 0x20;
        } else {
            if (used + 1 >= sizeof(framed)) return -1;
            framed[used++] = packet[i];
        }
    }
    framed[used++] = SHTP_UART_MARKER;
    // Match the BNO08x reference UART HAL's 1 ms inter-byte pacing. A single
    // 3 Mbps burst can overrun the sensor's receive path and produce SHTP errors.
    for (size_t i = 0; i < used; ++i) {
        if (uart_write_bytes(IMU_UART, (const char *)&framed[i], 1) != 1) return -1;
        if (uart_wait_tx_done(IMU_UART, pdMS_TO_TICKS(20)) != ESP_OK) return -1;
        esp_rom_delay_us(1000);
    }
    return (int)length;
}

static int imu_hal_open(sh2_Hal_t *hal)
{
    (void)hal;
    // Drop boot-time SHTP advertisements already queued before SH-2 starts.
    // The UART-SHTP reference HAL flushes RX before issuing its software reset;
    // otherwise SH-2 can consume a stale/partial startup packet as the reset reply.
    vTaskDelay(pdMS_TO_TICKS(200));
    uart_flush_input(IMU_UART);
    // SH-2 software reset, framed as a UART-SHTP transfer.
    const uint8_t reset[] = {5, 0, 1, 0, 1};
    int result = uart_frame_write(reset, sizeof(reset));
    ESP_LOGI(TAG, "BNO085 UART-SHTP reset sent after RX flush (%d bytes)", result);
    return result < 0 ? -1 : 0;
}

static void imu_hal_close(sh2_Hal_t *hal)
{
    (void)hal;
    uart_driver_delete(IMU_UART);
}

static int imu_hal_read(sh2_Hal_t *hal, uint8_t *buffer, unsigned capacity, uint32_t *timestamp_us)
{
    (void)hal;
    static bool in_frame, protocol_seen, escaped;
    static size_t used;
    static int64_t frame_start_us;
    unsigned bytes_this_service = 0;

    for (;;) {
        // Bound each service call even if a misconfigured sensor streams
        // continuously. Preserve parser state and resume on the next tick.
        if (++bytes_this_service > 256) return imu_hal_wait_for_data();
        size_t buffered = 0;
        if (uart_get_buffered_data_len(IMU_UART, &buffered) != ESP_OK || buffered == 0) {
            return imu_hal_wait_for_data();
        }
        uint8_t byte;
        int count = uart_read_bytes(IMU_UART, &byte, 1, 0);
        if (count <= 0) {
            if (in_frame && esp_timer_get_time() - frame_start_us > 20000) {
                in_frame = protocol_seen = escaped = false;
                used = 0;
            }
            return imu_hal_wait_for_data();
        }
        if (!in_frame) {
            if (byte == SHTP_UART_MARKER) {
                in_frame = true;
                frame_start_us = esp_timer_get_time();
                protocol_seen = false;
                escaped = false;
                used = 0;
            }
            continue;
        }
        if (!protocol_seen) {
            if (byte == SHTP_UART_MARKER) continue;
            if (byte != 0x01) {
                in_frame = false;
                continue;
            }
            protocol_seen = true;
            continue;
        }
        if (byte == SHTP_UART_MARKER && !escaped) {
            in_frame = protocol_seen = false;
            frame_start_us = 0;
            if (used < 4 || used > capacity) { used = 0; return 0; }
            uint16_t packet_length = (uint16_t)buffer[0] | ((uint16_t)buffer[1] << 8);
            packet_length &= 0x7fff;
            if (packet_length != used) { used = 0; return 0; }
            if (timestamp_us) *timestamp_us = (uint32_t)esp_timer_get_time();
            int result = (int)used;
            static unsigned debug_rx_frames;
            if (debug_rx_frames < 20) {
                ESP_LOGI(TAG, "BNO085 UART-SHTP RX frame=%u len=%d channel=%u",
                         debug_rx_frames, result, buffer[2]);
                ESP_LOG_BUFFER_HEX_LEVEL(TAG, buffer, result, ESP_LOG_INFO);
                debug_rx_frames++;
            }
            used = 0;
            return result;
        }
        if (!escaped && byte == SHTP_UART_ESCAPE) {
            escaped = true;
            continue;
        }
        if (escaped) { byte ^= 0x20; escaped = false; }
        if (used >= capacity) {
            in_frame = protocol_seen = escaped = false;
            frame_start_us = 0;
            used = 0;
            return imu_hal_wait_for_data();
        }
        buffer[used++] = byte;
        if (frame_start_us && esp_timer_get_time() - frame_start_us > 20000) {
            in_frame = protocol_seen = escaped = false;
            frame_start_us = 0;
            used = 0;
            return 0;
        }
    }
}

static int imu_hal_write(sh2_Hal_t *hal, uint8_t *buffer, unsigned length)
{
    (void)hal;
    static unsigned debug_tx_frames;
    if (debug_tx_frames < 20) {
        ESP_LOGI(TAG, "BNO085 UART-SHTP TX frame=%u len=%u channel=%u",
                 debug_tx_frames, (unsigned)length, length >= 3 ? buffer[2] : 0xff);
        ESP_LOG_BUFFER_HEX_LEVEL(TAG, buffer, length, ESP_LOG_INFO);
        debug_tx_frames++;
    }
    return uart_frame_write(buffer, length);
}

// Pre-solder UART bring-up monitor. It sends only the standard SH-2 software
// reset frame, then samples RX without starting the problematic SH-2 task.
static void imu_uart_diag_task(void *arg)
{
    (void)arg;
    uint32_t total = 0;
    uint8_t sample[16] = {0};
    size_t sample_len = 0;
    for (;;) {
        for (unsigned chunk = 0; chunk < 8; ++chunk) {
            size_t available = 0;
            if (uart_get_buffered_data_len(IMU_UART, &available) != ESP_OK || !available) break;
            uint8_t bytes[128];
            size_t request = available < sizeof(bytes) ? available : sizeof(bytes);
            int count = uart_read_bytes(IMU_UART, bytes, request, 0);
            if (count <= 0) break;
            total += (uint32_t)count;
            for (int i = 0; i < count && sample_len < sizeof(sample); ++i) {
                sample[sample_len++] = bytes[i];
            }
        }
        ESP_LOGI(TAG, "BNO085 passive UART RX total=%" PRIu32 " bytes sample_len=%u",
                 total, (unsigned)sample_len);
        if (sample_len) {
            ESP_LOG_BUFFER_HEX_LEVEL(TAG, sample, sample_len, ESP_LOG_INFO);
        }
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

static uint32_t imu_hal_time_us(sh2_Hal_t *hal)
{
    (void)hal;
    return (uint32_t)esp_timer_get_time();
}

static void imu_event(void *cookie, sh2_AsyncEvent_t *event)
{
    (void)cookie;
    if (event->eventId == SH2_RESET) {
        portENTER_CRITICAL(&imu_mux);
        imu_reset_seen = true;
        imu_report_us = 0;
        portEXIT_CRITICAL(&imu_mux);
        ESP_LOGI(TAG, "BNO085 SH-2 reset complete");
    }
}

static void imu_sensor_event(void *cookie, sh2_SensorEvent_t *event)
{
    (void)cookie;
    sh2_SensorValue_t value;
    if (sh2_decodeSensorEvent(&value, event) != SH2_OK || value.sensorId != SH2_ROTATION_VECTOR) return;
    const float x = value.un.rotationVector.i;
    const float y = value.un.rotationVector.j;
    const float z = value.un.rotationVector.k;
    const float w = value.un.rotationVector.real;
    const float yaw = atan2f(2.0f * (w * z + x * y), 1.0f - 2.0f * (y * y + z * z)) * 57.2957795f;
    const float pitch_term = 2.0f * (w * y - z * x);
    const float pitch = asinf(fmaxf(-1.0f, fminf(1.0f, pitch_term))) * 57.2957795f;
    const float roll = atan2f(2.0f * (w * x + y * z), 1.0f - 2.0f * (x * x + y * y)) * 57.2957795f;
    portENTER_CRITICAL(&imu_mux);
    imu_yaw = yaw; imu_pitch = pitch; imu_roll = roll;
    imu_report_us = esp_timer_get_time();
    portEXIT_CRITICAL(&imu_mux);
    static int64_t last_log_us;
    int64_t now_us = esp_timer_get_time();
    if (now_us - last_log_us >= 1000000) {
        last_log_us = now_us;
        ESP_LOGI(TAG, "BNO085 orientation yaw=%.1f pitch=%.1f roll=%.1f deg", yaw, pitch, roll);
    }
}

static void imu_task(void *arg)
{
    (void)arg;
    sh2_setSensorCallback(imu_sensor_event, NULL);
    ESP_LOGI(TAG, "BNO085 SH-2 service task started");
    bool report_enabled = false;
    int64_t last_config_attempt_us = 0;
    int64_t last_state_log_us = 0;
    int64_t last_reset_retry_us = esp_timer_get_time();
    unsigned reset_retries = 0;
    for (;;) {
        sh2_service();
        int64_t now_us = esp_timer_get_time();
        if (now_us - last_state_log_us >= 2000000) {
            last_state_log_us = now_us;
            ESP_LOGI(TAG, "BNO085 SH-2 state reset_seen=%d report_enabled=%d",
                     imu_reset_seen, report_enabled);
        }
        // Some breakouts power the BNO085 more slowly than the P4. Retry the
        // standard software reset a few times while the SH-2 reset event is
        // still absent; this is safe during bring-up and avoids a dead state.
        if (!imu_reset_seen && reset_retries < 3 && now_us - last_reset_retry_us >= 3000000) {
            static const uint8_t reset[] = {5, 0, 1, 0, 1};
            last_reset_retry_us = now_us;
            reset_retries++;
            int written = uart_frame_write(reset, sizeof(reset));
            ESP_LOGW(TAG, "BNO085 SH-2 reset retry %u/3 sent=%d bytes",
                     reset_retries, written);
        }
        if (imu_reset_seen && !report_enabled && now_us - last_config_attempt_us >= 1000000) {
            last_config_attempt_us = now_us;
            sh2_SensorConfig_t config = {0};
            config.reportInterval_us = IMU_REPORT_INTERVAL_US;
            int result = sh2_setSensorConfig(SH2_ROTATION_VECTOR, &config);
            if (result == SH2_OK) {
                report_enabled = true;
                ESP_LOGI(TAG, "BNO085 rotation-vector report enabled at 10 Hz");
            } else {
                ESP_LOGW(TAG, "BNO085 rotation-vector setup pending rc=%d", result);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(2));
    }
}

void hanmir_sensors_init(void)
{
    if (CONFIG_HANMIR_BAT_SDA_GPIO >= 0 && CONFIG_HANMIR_BAT_SCL_GPIO >= 0) {
        i2c_master_bus_config_t bus_config = {
            .i2c_port = I2C_NUM_1,
            .sda_io_num = CONFIG_HANMIR_BAT_SDA_GPIO,
            .scl_io_num = CONFIG_HANMIR_BAT_SCL_GPIO,
            .clk_source = I2C_CLK_SRC_DEFAULT,
            .glitch_ignore_cnt = 7,
            .flags.enable_internal_pullup = true,
        };
        i2c_master_bus_handle_t bus;
        if (i2c_new_master_bus(&bus_config, &bus) == ESP_OK) {
            i2c_device_config_t device_config = {
                .dev_addr_length = I2C_ADDR_BIT_LEN_7,
                .device_address = 0x36,
                .scl_speed_hz = 100000,
            };
            if (i2c_master_bus_add_device(bus, &device_config, &fuel_gauge) != ESP_OK) {
                ESP_LOGE(TAG, "MAX17048 add failed");
            }
        } else ESP_LOGE(TAG, "MAX17048 I2C bus init failed");
    } else ESP_LOGW(TAG, "MAX17048 GPIOs not verified; battery reports unknown");
#ifdef CONFIG_HANMIR_ENABLE_BNO_SH2
    if (CONFIG_HANMIR_IMU_RX_GPIO >= 0 && CONFIG_HANMIR_IMU_TX_GPIO >= 0) {
        uart_config_t config = {
            .baud_rate = IMU_UART_BAUD, .data_bits = UART_DATA_8_BITS,
            .parity = UART_PARITY_DISABLE, .stop_bits = UART_STOP_BITS_1,
            .flow_ctrl = UART_HW_FLOWCTRL_DISABLE, .source_clk = UART_SCLK_DEFAULT,
        };
        esp_err_t err = uart_param_config(IMU_UART, &config);
        if (err == ESP_OK) err = uart_set_pin(IMU_UART, CONFIG_HANMIR_IMU_TX_GPIO,
                                               CONFIG_HANMIR_IMU_RX_GPIO,
                                               UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
        if (err == ESP_OK) err = uart_driver_install(IMU_UART, 4096, 1024, 0, NULL, 0);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "BNO085 UART setup failed: %s", esp_err_to_name(err));
            return;
        }
        imu_hal.open = imu_hal_open; imu_hal.close = imu_hal_close;
        imu_hal.read = imu_hal_read; imu_hal.write = imu_hal_write;
        imu_hal.getTimeUs = imu_hal_time_us;
        int rc = sh2_open(&imu_hal, imu_event, NULL);
        ESP_LOGI(TAG, "BNO085 sh2_open rc=%d reset_seen=%d", rc, imu_reset_seen);
        if (rc != SH2_OK) {
            ESP_LOGE(TAG, "BNO085 SH-2 open failed rc=%d; check UART-SHTP mode and wiring", rc);
            uart_driver_delete(IMU_UART);
            return;
        }
        if (xTaskCreate(imu_task, "bno085_sh2", 6144, NULL, 5, NULL) != pdPASS) {
            ESP_LOGE(TAG, "BNO085 task creation failed");
            sh2_close();
            return;
        }
        ESP_LOGI(TAG, "BNO085 UART-SHTP listening GPIO RX%d/TX%d at %d baud",
                 CONFIG_HANMIR_IMU_RX_GPIO, CONFIG_HANMIR_IMU_TX_GPIO, IMU_UART_BAUD);
    } else if (CONFIG_HANMIR_IMU_RX_GPIO >= 0 || CONFIG_HANMIR_IMU_TX_GPIO >= 0) {
        ESP_LOGW(TAG, "BNO085 needs both UART RX and TX GPIOs");
    }
#else
    if (CONFIG_HANMIR_IMU_RX_GPIO >= 0 && CONFIG_HANMIR_IMU_TX_GPIO >= 0) {
        uart_config_t config = {
            .baud_rate = IMU_UART_BAUD, .data_bits = UART_DATA_8_BITS,
            .parity = UART_PARITY_DISABLE, .stop_bits = UART_STOP_BITS_1,
            .flow_ctrl = UART_HW_FLOWCTRL_DISABLE, .source_clk = UART_SCLK_DEFAULT,
        };
        esp_err_t err = uart_param_config(IMU_UART, &config);
        if (err == ESP_OK) err = uart_set_pin(IMU_UART, CONFIG_HANMIR_IMU_TX_GPIO,
                                               CONFIG_HANMIR_IMU_RX_GPIO,
                                               UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
        if (err == ESP_OK) err = uart_driver_install(IMU_UART, 4096, 0, 0, NULL, 0);
        const uint8_t reset_packet[] = {5, 0, 1, 0, 1};
        int reset_result = err == ESP_OK ? uart_frame_write(reset_packet, sizeof(reset_packet)) : -1;
        if (err == ESP_OK && reset_result >= 0 && xTaskCreate(imu_uart_diag_task, "bno_uart_diag", 3072,
                                         NULL, 2, NULL) == pdPASS) {
            ESP_LOGW(TAG, "BNO085 UART diagnostic RX%d/TX%d at %d baud; reset sent (%d bytes), SH-2 disabled",
                     CONFIG_HANMIR_IMU_RX_GPIO, CONFIG_HANMIR_IMU_TX_GPIO, IMU_UART_BAUD, reset_result);
        } else {
            ESP_LOGE(TAG, "BNO085 UART diagnostic setup/reset failed: init=%s tx=%d",
                     esp_err_to_name(err), reset_result);
            if (err == ESP_OK) uart_driver_delete(IMU_UART);
        }
    } else {
        ESP_LOGW(TAG, "BNO085 GPIOs not configured; UART monitor unavailable");
    }
#endif
}

bool hanmir_battery_percent(float *percent)
{
    if (!percent || !fuel_gauge) return false;
    uint8_t reg = 0x04, data[2];
    if (i2c_master_transmit_receive(fuel_gauge, &reg, 1, data, 2, 100) != ESP_OK) return false;
    float soc = (float)data[0] + (float)data[1] / 256.0f;
    if (soc < 0 || soc > 100) return false;
    *percent = soc;
    return true;
}

bool hanmir_imu_ready(void)
{
    portENTER_CRITICAL(&imu_mux);
    bool ready = imu_report_us > 0 && esp_timer_get_time() - imu_report_us < 2000000;
    portEXIT_CRITICAL(&imu_mux);
    return ready;
}

bool hanmir_imu_orientation(float *yaw, float *pitch, float *roll)
{
    portENTER_CRITICAL(&imu_mux);
    bool ready = imu_report_us > 0 && esp_timer_get_time() - imu_report_us < 2000000;
    if (ready) {
        if (yaw) *yaw = imu_yaw;
        if (pitch) *pitch = imu_pitch;
        if (roll) *roll = imu_roll;
    }
    portEXIT_CRITICAL(&imu_mux);
    return ready;
}
