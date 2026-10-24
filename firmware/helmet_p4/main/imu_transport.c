#include "imu_monitor.h"
#include "hanmir.h"
#include "esp_timer.h"
#include "esp_websocket_client.h"
#include "esp_random.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>

static const char *TAG="hanmir_imu_tx";
static QueueHandle_t samples, events;
static esp_websocket_client_handle_t client;
static atomic_ullong capture_until_us;
static atomic_uint queued, sent, overflow, aged, failed, event_overflow, wire_bytes, max_send_us;
static atomic_uint tx_stack_min;
static uint32_t boot_id;

bool hanmir_imu_capture_set(bool enabled, unsigned duration_s)
{
    if (enabled && (duration_s<1 || duration_s>1800)) return false;
    atomic_store(&capture_until_us,enabled?esp_timer_get_time()+duration_s*1000000ULL:0);
    return true;
}

void hanmir_imu_transport_submit(const hanmir_imu_record_t *record)
{
#ifdef CONFIG_HANMIR_IMU_FALL_SHADOW
    bool event=record->kind>=100;
    if (!event && (uint64_t)esp_timer_get_time()>=atomic_load(&capture_until_us)) return;
    QueueHandle_t destination=event?events:samples;
    if (!destination || xQueueSend(destination,record,0)!=pdTRUE) {
        atomic_fetch_add(event?&event_overflow:&overflow,1);return;
    }
    atomic_fetch_add(&queued,1);
#endif
}

void hanmir_imu_transport_status(cJSON *object)
{
    uint64_t now=esp_timer_get_time(), until=atomic_load(&capture_until_us);
    cJSON_AddBoolToObject(object,"capture_active",until>now);
    cJSON_AddNumberToObject(object,"capture_remaining_ms",until>now?(until-now)/1000.0:0);
    cJSON_AddNumberToObject(object,"telemetry_queued",atomic_load(&queued));
    cJSON_AddNumberToObject(object,"telemetry_sent",atomic_load(&sent));
    cJSON_AddNumberToObject(object,"telemetry_overflow",atomic_load(&overflow));
    cJSON_AddNumberToObject(object,"telemetry_aged",atomic_load(&aged));
    cJSON_AddNumberToObject(object,"telemetry_send_failed",atomic_load(&failed));
    cJSON_AddNumberToObject(object,"event_overflow",atomic_load(&event_overflow));
    cJSON_AddNumberToObject(object,"telemetry_wire_bytes",atomic_load(&wire_bytes));
    cJSON_AddNumberToObject(object,"telemetry_max_send_us",atomic_load(&max_send_us));
    cJSON_AddNumberToObject(object,"telemetry_queue_depth",samples?uxQueueMessagesWaiting(samples):0);
    cJSON_AddNumberToObject(object,"event_queue_depth",events?uxQueueMessagesWaiting(events):0);
    cJSON_AddBoolToObject(object,"telemetry_connected",client&&esp_websocket_client_is_connected(client));
    cJSON_AddNumberToObject(object,"tx_stack_min",atomic_load(&tx_stack_min));
}

static void transport_task(void *arg)
{
    (void)arg;
    uint32_t batch=0;
    int64_t last_log=0;
    for (;;) {
        uint64_t now=esp_timer_get_time();
        if (hanmir_network_online() && esp_websocket_client_is_connected(client)) {
            hanmir_imu_record_t records[16];
            unsigned count=0;
            // Keep diagnostic events ahead of bulk samples. Failed events are
            // returned to their bounded queue; samples use explicit loss counters.
            while (count<16 && xQueueReceive(events,&records[count],0)==pdTRUE) count++;
            hanmir_imu_record_t sample;
            while (count<16 && xQueueReceive(samples,&sample,0)==pdTRUE) {
                if (now>sample.received_us && now-sample.received_us>500000) {
                    atomic_fetch_add(&aged,1);continue;
                }
                records[count++]=sample;
            }
            if (count) {
                cJSON *root=cJSON_CreateObject();
                if (root) {
                    char boot[16];snprintf(boot,sizeof(boot),"%08lx",(unsigned long)boot_id);
                    cJSON_AddStringToObject(root,"type","imu_batch");
                    cJSON_AddStringToObject(root,"boot",boot);
                    cJSON_AddNumberToObject(root,"v",1);
                    cJSON_AddNumberToObject(root,"batch",++batch);
                    cJSON_AddNumberToObject(root,"tx_us",esp_timer_get_time());
                    cJSON *items=cJSON_AddArrayToObject(root,"records");
                    for (unsigned i=0;i<count;i++) {
                        double values[]={records[i].kind,records[i].sequence,records[i].status,
                            (double)records[i].sensor_us,(double)records[i].received_us,
                            records[i].x,records[i].y,records[i].z,records[i].w};
                        cJSON_AddItemToArray(items,cJSON_CreateDoubleArray(values,9));
                    }
                    cJSON *metrics=cJSON_AddObjectToObject(root,"metrics");
                    hanmir_imu_monitor_status(metrics);
                    char packet[6144];
                    bool encoded=cJSON_PrintPreallocated(root,packet,sizeof(packet),false);
                    cJSON_Delete(root);
                    int length=encoded?(int)strlen(packet):0;
                    int64_t started=esp_timer_get_time();
                    int result=length?esp_websocket_client_send_text(client,packet,length,pdMS_TO_TICKS(30)):-1;
                    unsigned elapsed=(unsigned)(esp_timer_get_time()-started);
                    unsigned previous=atomic_load(&max_send_us);
                    if (elapsed>previous) atomic_store(&max_send_us,elapsed);
                    if (result==length && length>0) {
                        atomic_fetch_add(&sent,count);atomic_fetch_add(&wire_bytes,length);
                    } else {
                        for (unsigned i=0;i<count;i++) {
                            atomic_fetch_add(&failed,1);
                            if (records[i].kind>=100 && xQueueSend(events,&records[i],0)!=pdTRUE)
                                atomic_fetch_add(&event_overflow,1);
                        }
                    }
                } else {
                    for (unsigned i=0;i<count;i++) {
                        atomic_fetch_add(&failed,1);
                        if (records[i].kind>=100 && xQueueSend(events,&records[i],0)!=pdTRUE)
                            atomic_fetch_add(&event_overflow,1);
                    }
                }
            }
        } else {
            // Do not retain stale bulk telemetry during long outages.
            hanmir_imu_record_t old;
            while (samples && uxQueueMessagesWaiting(samples)>96 && xQueueReceive(samples,&old,0)==pdTRUE)
                atomic_fetch_add(&aged,1);
        }
        if ((int64_t)now-last_log>=5000000) {
            last_log=(int64_t)now;
            atomic_store(&tx_stack_min,(uint32_t)uxTaskGetStackHighWaterMark(NULL));
            ESP_LOGI(TAG,"shadow capture=%d sent=%u overflow=%u aged=%u failed=%u event_overflow=%u tx_stack_min=%u",
                now<atomic_load(&capture_until_us),(unsigned)atomic_load(&sent),(unsigned)atomic_load(&overflow),
                (unsigned)atomic_load(&aged),(unsigned)atomic_load(&failed),(unsigned)atomic_load(&event_overflow),
                (unsigned)atomic_load(&tx_stack_min));
        }
        // Raw diagnostics only: enough service headroom for ~125 reports/s.
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

esp_err_t hanmir_imu_transport_start(void)
{
#ifdef CONFIG_HANMIR_IMU_FALL_SHADOW
    if (!CONFIG_HANMIR_SERVER_HOST[0] || !CONFIG_HANMIR_CALL_DEVICE_TOKEN[0]) return ESP_ERR_INVALID_STATE;
    samples=xQueueCreate(128,sizeof(hanmir_imu_record_t));
    events=xQueueCreate(16,sizeof(hanmir_imu_record_t));
    if (!samples||!events) return ESP_ERR_NO_MEM;
    boot_id=esp_random();
    static char uri[256],headers[256];
    snprintf(uri,sizeof(uri),"ws://%s:%d/api/imu/stream/%s",CONFIG_HANMIR_SERVER_HOST,
        CONFIG_HANMIR_SERVER_PORT,CONFIG_HANMIR_DEVICE_ID);
    snprintf(headers,sizeof(headers),"Authorization: Bearer %s\r\n",CONFIG_HANMIR_CALL_DEVICE_TOKEN);
    esp_websocket_client_config_t config={.uri=uri,.headers=headers,.buffer_size=1024,
        .network_timeout_ms=1000,.reconnect_timeout_ms=3000,.task_stack=4096};
    client=esp_websocket_client_init(&config);
    if (!client) return ESP_ERR_NO_MEM;
    esp_err_t result=esp_websocket_client_start(client);
    if (result!=ESP_OK) return result;
    return xTaskCreate(transport_task,"imu_tx",16384,NULL,2,NULL)==pdPASS?ESP_OK:ESP_ERR_NO_MEM;
#else
    return ESP_OK;
#endif
}
