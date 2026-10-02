#include "hanmir.h"
#include "driver/i2c_master.h"
#include "esp_log.h"

static const char *TAG = "hanmir_sensors";
static i2c_master_dev_handle_t fuel_gauge;

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
    if (CONFIG_HANMIR_IMU_RX_GPIO >= 0 || CONFIG_HANMIR_IMU_TX_GPIO >= 0) {
        ESP_LOGW(TAG, "BNO085 UART pins set, but SHTP reports need board mode/baud verification before enabling fall decisions");
    }
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

bool hanmir_imu_ready(void) { return false; }
