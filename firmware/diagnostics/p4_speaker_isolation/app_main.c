#include <math.h>
#include <stdio.h>
#include "driver/i2s_std.h"
#include "driver/pulse_cnt.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "speaker_isolation";
static const int pins[3] = {20, 21, 22};
static pcnt_unit_handle_t counters[3];
static void counters_init(void) {
    for (int i=0;i<3;i++) {
        pcnt_unit_config_t u={.low_limit=-32768,.high_limit=32767,.flags.accum_count=true};
        ESP_ERROR_CHECK(pcnt_new_unit(&u,&counters[i]));
        pcnt_chan_config_t c={.edge_gpio_num=pins[i],.level_gpio_num=-1,.flags.io_loop_back=true};
        pcnt_channel_handle_t ch;
        ESP_ERROR_CHECK(pcnt_new_channel(counters[i],&c,&ch));
        ESP_ERROR_CHECK(pcnt_channel_set_edge_action(ch,PCNT_CHANNEL_EDGE_ACTION_INCREASE,PCNT_CHANNEL_EDGE_ACTION_HOLD));
        ESP_ERROR_CHECK(pcnt_channel_set_level_action(ch,PCNT_CHANNEL_LEVEL_ACTION_KEEP,PCNT_CHANNEL_LEVEL_ACTION_KEEP));
        ESP_ERROR_CHECK(pcnt_unit_add_watch_point(counters[i],32767));
        ESP_ERROR_CHECK(pcnt_unit_add_watch_point(counters[i],-32768));
        ESP_ERROR_CHECK(pcnt_unit_enable(counters[i]));
        ESP_ERROR_CHECK(pcnt_unit_start(counters[i]));
    }
}
static void phase(int num,int port,int bits,int stereo,int right,int rate) {
    ESP_LOGI(TAG,"PHASE %d port=%d bits=%d stereo=%d right=%d rate=%d",num,port,bits,stereo,right,rate);
    i2s_chan_config_t cc=I2S_CHANNEL_DEFAULT_CONFIG(port,I2S_ROLE_MASTER);
    cc.dma_desc_num=6;cc.dma_frame_num=160;cc.auto_clear_after_cb=true;
    i2s_chan_handle_t tx;
    ESP_ERROR_CHECK(i2s_new_channel(&cc,&tx,NULL));
    i2s_std_config_t cfg={
        .clk_cfg=I2S_STD_CLK_DEFAULT_CONFIG(rate),
        .slot_cfg=I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(bits,stereo?I2S_SLOT_MODE_STEREO:I2S_SLOT_MODE_MONO),
        .gpio_cfg={.mclk=I2S_GPIO_UNUSED,.bclk=20,.ws=21,.dout=22,.din=I2S_GPIO_UNUSED}
    };
    cfg.slot_cfg.slot_mask=stereo?I2S_STD_SLOT_BOTH:(right?I2S_STD_SLOT_RIGHT:I2S_STD_SLOT_LEFT);
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(tx,&cfg));
    if(num==1)counters_init();
    for(int i=0;i<3;i++)ESP_ERROR_CHECK(pcnt_unit_clear_count(counters[i]));
    gpio_dump_io_configuration(stdout,(1ULL<<20)|(1ULL<<21)|(1ULL<<22));
    ESP_ERROR_CHECK(i2s_channel_enable(tx));
    int64_t start=esp_timer_get_time();
    size_t written_total=0;int samples=0;static int16_t buf16[640];static int32_t buf32[640];
    while(samples<rate) {
        int frames=(rate-samples)>320?320:rate-samples;int slots=stereo?2:1;
        for(int i=0;i<frames;i++) {
            int16_t val=(int16_t)(6000*sin(2*3.141592653589793*1000*(samples+i)/rate));
            for(int j=0;j<slots;j++) {buf16[i*slots+j]=val;buf32[i*slots+j]=(int32_t)val*65536;}
        }
        size_t expected=frames*slots*(bits/8),written=0;
        esp_err_t err=i2s_channel_write(tx,bits==16?(void*)buf16:(void*)buf32,expected,&written,1000);
        written_total+=written;
        if(err!=ESP_OK||written!=expected) {ESP_LOGE(TAG,"write err=%s written=%u expected=%u",esp_err_to_name(err),(unsigned)written,(unsigned)expected);break;}
        samples+=frames;
    }
    vTaskDelay(pdMS_TO_TICKS(150));
    int counts[3];for(int i=0;i<3;i++)ESP_ERROR_CHECK(pcnt_unit_get_count(counters[i],&counts[i]));
    ESP_LOGI(TAG,"PHASE %d DONE samples=%d bytes=%u elapsed_us=%lld BCLK_edges=%d WS_edges=%d DATA_edges=%d",num,samples,(unsigned)written_total,(long long)(esp_timer_get_time()-start),counts[0],counts[1],counts[2]);
    ESP_ERROR_CHECK(i2s_channel_disable(tx));ESP_ERROR_CHECK(i2s_del_channel(tx));
    vTaskDelay(pdMS_TO_TICKS(2000));
}
static void pin_crosscheck(void) {
    ESP_LOGW(TAG,"PIN CROSSCHECK: I2S disabled; one GPIO output at a time, others input/pulldown.");
    for(int active=0;active<3;active++) {
        for(int i=0;i<3;i++) {ESP_ERROR_CHECK(gpio_reset_pin(pins[i]));ESP_ERROR_CHECK(gpio_set_direction(pins[i],GPIO_MODE_INPUT));ESP_ERROR_CHECK(gpio_set_pull_mode(pins[i],GPIO_PULLDOWN_ONLY));}
        ESP_ERROR_CHECK(gpio_set_direction(pins[active],GPIO_MODE_INPUT_OUTPUT));
        ESP_ERROR_CHECK(gpio_set_level(pins[active],0));vTaskDelay(pdMS_TO_TICKS(20));
        int lo[3],hi[3];for(int i=0;i<3;i++)lo[i]=gpio_get_level(pins[i]);
        ESP_ERROR_CHECK(gpio_set_level(pins[active],1));vTaskDelay(pdMS_TO_TICKS(20));
        for(int i=0;i<3;i++)hi[i]=gpio_get_level(pins[i]);
        ESP_LOGW(TAG,"DRIVE GPIO%d LOW=%d,%d,%d HIGH=%d,%d,%d (order 20,21,22)",pins[active],lo[0],lo[1],lo[2],hi[0],hi[1],hi[2]);
        for(int i=0;i<3;i++)ESP_ERROR_CHECK(pcnt_unit_clear_count(counters[i]));
        for(int k=0;k<100;k++){gpio_set_level(pins[active],0);vTaskDelay(pdMS_TO_TICKS(2));gpio_set_level(pins[active],1);vTaskDelay(pdMS_TO_TICKS(2));}
        int c[3];for(int i=0;i<3;i++)ESP_ERROR_CHECK(pcnt_unit_get_count(counters[i],&c[i]));
        ESP_LOGW(TAG,"DRIVE GPIO%d 100 PULSES COUNTS=%d,%d,%d",pins[active],c[0],c[1],c[2]);
        gpio_set_level(pins[active],0);
    }
    for(int i=0;i<3;i++){gpio_reset_pin(pins[i]);gpio_set_direction(pins[i],GPIO_MODE_INPUT);gpio_set_pull_mode(pins[i],GPIO_PULLDOWN_ONLY);}
}
void app_main(void) {
    ESP_LOGW(TAG,"DIAGNOSTIC ONLY: no network/camera/microphone/IMU/call tasks. Tones start in 10 seconds.");
    vTaskDelay(pdMS_TO_TICKS(10000));
    phase(1,1,16,0,0,16000);
    phase(2,1,16,0,1,16000);
    phase(3,1,16,1,0,16000);
    phase(4,1,32,1,0,16000);
    phase(5,0,16,1,0,16000);
    phase(6,1,16,1,0,48000);
    pin_crosscheck();
    ESP_LOGW(TAG,"DIAGNOSTIC COMPLETE: staying silent. Restore normal firmware after comparison.");
    for(;;)vTaskDelay(pdMS_TO_TICKS(1000));
}
