#include <stdio.h>
#include "driver/gpio.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
static const int pins[3]={20,21,22};
void app_main(void){
    vTaskDelay(pdMS_TO_TICKS(4000));
    ESP_LOGW("pin_only","INDEPENDENT GPIO TEST: no I2S and no PCNT initialized");
    for(int repeat=0;repeat<2;repeat++)for(int a=0;a<3;a++){
        for(int i=0;i<3;i++){
            ESP_ERROR_CHECK(gpio_reset_pin(pins[i]));
            ESP_ERROR_CHECK(gpio_set_direction(pins[i],GPIO_MODE_INPUT));
            ESP_ERROR_CHECK(gpio_set_pull_mode(pins[i],GPIO_PULLDOWN_ONLY));
        }
        ESP_ERROR_CHECK(gpio_set_direction(pins[a],GPIO_MODE_INPUT_OUTPUT));
        for(int level=0;level<2;level++){
            gpio_set_level(pins[a],level);vTaskDelay(pdMS_TO_TICKS(100));
            ESP_LOGW("pin_only","repeat=%d output=GPIO%d level=%d READ_20_21_22=%d,%d,%d",repeat,pins[a],level,gpio_get_level(20),gpio_get_level(21),gpio_get_level(22));
        }
        gpio_dump_io_configuration(stdout,(1ULL<<20)|(1ULL<<21)|(1ULL<<22));
    }
    for(int i=0;i<3;i++){gpio_reset_pin(pins[i]);gpio_set_direction(pins[i],GPIO_MODE_INPUT);gpio_set_pull_mode(pins[i],GPIO_PULLDOWN_ONLY);}
    ESP_LOGW("pin_only","COMPLETE");for(;;)vTaskDelay(pdMS_TO_TICKS(1000));
}
