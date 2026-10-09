#include "hanmir.h"
#include "esp_log.h"

static const char *TAG = "hanmir_pin_guard";

typedef struct { const char *name; int pin; } pin_assignment_t;

static bool reserved(int pin)
{
    return pin == 3 || pin == 6 || pin == 7 || pin == 8 || pin == 9 ||
           pin == 12 || (pin >= 14 && pin <= 19) || pin == 35 ||
           (pin >= 37 && pin <= 45) || pin == 54;
}

esp_err_t hanmir_pin_guard_validate(void)
{
    const pin_assignment_t pins[] = {
        {"mic BCLK", CONFIG_HANMIR_MIC_BCLK_GPIO},
        {"mic WS", CONFIG_HANMIR_MIC_WS_GPIO},
        {"mic DATA", CONFIG_HANMIR_MIC_DATA_GPIO},
        {"speaker BCLK", CONFIG_HANMIR_SPK_BCLK_GPIO},
        {"speaker WS", CONFIG_HANMIR_SPK_WS_GPIO},
        {"speaker DIN", CONFIG_HANMIR_SPK_DATA_GPIO},
        {"battery SDA", CONFIG_HANMIR_BAT_SDA_GPIO},
        {"battery SCL", CONFIG_HANMIR_BAT_SCL_GPIO},
        {"IMU RX", CONFIG_HANMIR_IMU_RX_GPIO},
        {"IMU TX", CONFIG_HANMIR_IMU_TX_GPIO},
    };
    for (unsigned i = 0; i < sizeof(pins) / sizeof(pins[0]); ++i) {
        if (pins[i].pin < 0) continue;
        if (pins[i].pin > 54 || reserved(pins[i].pin)) {
            ESP_LOGE(TAG, "%s GPIO%d conflicts with a DFR1172 reserved resource", pins[i].name, pins[i].pin);
            return ESP_ERR_INVALID_ARG;
        }
        for (unsigned j = i + 1; j < sizeof(pins) / sizeof(pins[0]); ++j) {
            if (pins[i].pin == pins[j].pin) {
                ESP_LOGE(TAG, "GPIO%d shared by %s and %s", pins[i].pin, pins[i].name, pins[j].name);
                return ESP_ERR_INVALID_ARG;
            }
        }
    }
    ESP_LOGI(TAG, "external GPIO assignments have no reserved or duplicate pins");
    return ESP_OK;
}
