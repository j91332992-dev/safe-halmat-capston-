#include <stdbool.h>
#include <stdint.h>

#include "driver/i2c_master.h"
#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

/*
 * HANMIR MAX17048 standalone test
 *
 * Wiring from the final wiring table:
 *   MAX17048 SDA -> DFR1172 P2 GPIO33
 *   MAX17048 SCL -> DFR1172 P2 GPIO32
 *   MAX17048 logic supply -> DFR1172 3V3
 *   MAX17048 battery JST -> battery B+ / B- (the SW6106 B+ / B- points)
 *
 * This program intentionally starts no Wi-Fi, camera, audio, or server task.
 */

#define MAX17048_I2C_PORT       I2C_NUM_1
#define MAX17048_SCL_GPIO       GPIO_NUM_32
#define MAX17048_SDA_GPIO       GPIO_NUM_33
#define MAX17048_I2C_ADDR       0x36
#define MAX17048_I2C_SPEED_HZ   100000
#define I2C_TIMEOUT_MS          1000
#define READ_INTERVAL_MS        2000

/* MAX17048 registers */
#define MAX17048_REG_VCELL      0x02
#define MAX17048_REG_SOC        0x04
#define MAX17048_REG_VERSION    0x08

static const char *TAG = "MAX17048_TEST";

static esp_err_t max17048_read_u16(i2c_master_dev_handle_t device,
                                   uint8_t reg,
                                   uint16_t *value)
{
    uint8_t data[2] = {0};
    esp_err_t err = i2c_master_transmit_receive(device, &reg, 1, data, sizeof(data),
                                                 I2C_TIMEOUT_MS);
    if (err != ESP_OK) {
        return err;
    }

    *value = ((uint16_t)data[0] << 8) | data[1];
    return ESP_OK;
}

static void scan_i2c_bus(i2c_master_bus_handle_t bus, bool *max17048_found)
{
    *max17048_found = false;
    ESP_LOGI(TAG, "I2C1 scan start: SDA=GPIO%d, SCL=GPIO%d", MAX17048_SDA_GPIO,
             MAX17048_SCL_GPIO);

    for (uint8_t address = 0x08; address < 0x78; ++address) {
        if (i2c_master_probe(bus, address, I2C_TIMEOUT_MS) == ESP_OK) {
            ESP_LOGI(TAG, "I2C response: 0x%02X%s", address,
                     address == MAX17048_I2C_ADDR ? "  <-- expected MAX17048" : "");
            if (address == MAX17048_I2C_ADDR) {
                *max17048_found = true;
            }
        }
    }

    if (!*max17048_found) {
        ESP_LOGE(TAG, "MAX17048 was not found at 0x36");
        ESP_LOGE(TAG, "Check 3.3V, common ground, SDA=GPIO33, SCL=GPIO32, and the battery JST.");
    }
}

void app_main(void)
{
    ESP_LOGI(TAG, "MAX17048 standalone test started");
    ESP_LOGI(TAG, "No Wi-Fi, camera, microphone, speaker, or server connection is started.");

    i2c_master_bus_config_t bus_config = {
        .i2c_port = MAX17048_I2C_PORT,
        .sda_io_num = MAX17048_SDA_GPIO,
        .scl_io_num = MAX17048_SCL_GPIO,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };

    i2c_master_bus_handle_t bus = NULL;
    ESP_ERROR_CHECK(i2c_new_master_bus(&bus_config, &bus));

    bool found = false;
    scan_i2c_bus(bus, &found);
    if (!found) {
        while (true) {
            vTaskDelay(pdMS_TO_TICKS(READ_INTERVAL_MS));
            scan_i2c_bus(bus, &found);
            if (found) {
                break;
            }
        }
    }

    i2c_device_config_t device_config = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = MAX17048_I2C_ADDR,
        .scl_speed_hz = MAX17048_I2C_SPEED_HZ,
    };

    i2c_master_dev_handle_t fuel_gauge = NULL;
    ESP_ERROR_CHECK(i2c_master_bus_add_device(bus, &device_config, &fuel_gauge));

    uint16_t version = 0;
    if (max17048_read_u16(fuel_gauge, MAX17048_REG_VERSION, &version) == ESP_OK) {
        ESP_LOGI(TAG, "MAX17048 version register: 0x%04X", version);
    } else {
        ESP_LOGW(TAG, "Version register read failed; continuing with voltage/SOC reads");
    }

    while (true) {
        uint16_t vcell_raw = 0;
        uint16_t soc_raw = 0;
        esp_err_t voltage_err = max17048_read_u16(fuel_gauge, MAX17048_REG_VCELL, &vcell_raw);
        esp_err_t soc_err = max17048_read_u16(fuel_gauge, MAX17048_REG_SOC, &soc_raw);

        if (voltage_err != ESP_OK || soc_err != ESP_OK) {
            ESP_LOGE(TAG, "Read failed: VCELL=%s, SOC=%s. Recheck I2C wiring and power.",
                     esp_err_to_name(voltage_err), esp_err_to_name(soc_err));
        } else {
            /* VCELL LSB is 78.125 microvolts; SOC is an 8.8 fixed-point percent. */
            float voltage_v = (float)vcell_raw * 0.000078125f;
            float soc_percent = (float)soc_raw / 256.0f;
            ESP_LOGI(TAG, "BATTERY: voltage=%.3f V, SOC=%.1f %%", voltage_v, soc_percent);
        }

        vTaskDelay(pdMS_TO_TICKS(READ_INTERVAL_MS));
    }
}
