// Pilot shadow detector. No speaker/API action; server wake/emergency path remains.
#include "local_wake.h"
#include "sdkconfig.h"
#if CONFIG_HANMIR_LOCAL_WAKE_SHADOW
#include <atomic>
#include <cstring>
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "tutus_frontend.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/micro_resource_variable.h"
#include "tensorflow/lite/schema/schema_generated.h"
extern const unsigned char model_bytes[] asm("_binary_tutus_pilot_tflite_start");
namespace {
const char *TAG="tutus_shadow";
struct Block {int16_t pcm[160]; uint32_t seq; int64_t queued_us; bool eligible;};
QueueHandle_t queue;
std::atomic<bool> ready{false};
std::atomic<uint32_t> drops{0};
void task(void *) {
    const auto *model=tflite::GetModel(model_bytes);
    static tflite::MicroMutableOpResolver<13> ops;
    bool ok=model->version()==TFLITE_SCHEMA_VERSION;
#define ADD(name) ok=ops.Add##name()==kTfLiteOk && ok
    ADD(AssignVariable); ADD(CallOnce); ADD(Concatenation); ADD(Conv2D);
    ADD(DepthwiseConv2D); ADD(FullyConnected); ADD(Logistic); ADD(Quantize);
    ADD(ReadVariable); ADD(Reshape); ADD(SplitV); ADD(StridedSlice); ADD(VarHandle);
#undef ADD
    auto *arena=static_cast<uint8_t*>(heap_caps_aligned_alloc(16,32768,MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT));
    if(!ok || !arena) {heap_caps_free(arena); ESP_LOGE(TAG,"init allocation/ops failed; server path retained"); vTaskDelete(nullptr); return;}
    auto *allocator=tflite::MicroAllocator::Create(arena,32768);
    auto *variables=allocator ? tflite::MicroResourceVariables::Create(allocator,12) : nullptr;
    if(!variables) {heap_caps_free(arena); ESP_LOGE(TAG,"resource init failed"); vTaskDelete(nullptr); return;}
    tflite::MicroInterpreter interpreter(model,ops,allocator,variables);
    if(interpreter.AllocateTensors()!=kTfLiteOk || !tutus_frontend_init()) {
        tutus_frontend_free(); heap_caps_free(arena);
        ESP_LOGE(TAG,"model/frontend init failed; server path retained"); vTaskDelete(nullptr); return;
    }
    auto *input=interpreter.input(0); auto *output=interpreter.output(0);
    if(input->type!=kTfLiteInt8 || input->bytes!=120 || output->type!=kTfLiteUInt8) {
        tutus_frontend_free(); heap_caps_free(arena);
        ESP_LOGE(TAG,"tensor contract failed"); vTaskDelete(nullptr); return;
    }
    ESP_LOGI(TAG,"ready SHADOW_ONLY model=v2 arena=%u observation_threshold=.70 confirmations=1 warmup_ms=1500",
        (unsigned)interpreter.arena_used_bytes());
    ready=true;
    Block block; uint32_t previous=0, seen=0, invocations=0, hits=0;
    int fill=0, streak=0; bool window_eligible=true;
    int64_t report_at=esp_timer_get_time(), last_hit=0, max_us=0, max_queue_us=0;
    uint32_t deadline_misses=0;
    float peak=0;
    for(;;) {
        if(xQueueReceive(queue,&block,portMAX_DELAY)!=pdTRUE) continue;
        if(previous && block.seq!=previous+1) {
            if(interpreter.Reset()!=kTfLiteOk || !tutus_frontend_init()) {
                ready=false; tutus_frontend_free(); heap_caps_free(arena);
                ESP_LOGE(TAG,"reset failed"); vTaskDelete(nullptr); return;
            }
            seen=0; fill=0; streak=0; window_eligible=true;
            ESP_LOGW(TAG,"PCM gap; state reset and warmup restarted");
        }
        previous=block.seq; ++seen;
        int64_t start=esp_timer_get_time(), age=start-block.queued_us;
        if(age>max_queue_us) max_queue_us=age;
        float features[40];
        if(!tutus_frontend_process(block.pcm,features)) continue;
        window_eligible=window_eligible && block.eligible;
        for(int n=0;n<40;++n) {
            float q=features[n]/input->params.scale+input->params.zero_point;
            q=q>127?127:(q< -128? -128:q);
            input->data.int8[fill*40+n]=(int8_t)q;
        }
        if(++fill<3) continue;
        fill=0;
        if(interpreter.Invoke()!=kTfLiteOk) {
            ready=false; tutus_frontend_free(); heap_caps_free(arena);
            ESP_LOGE(TAG,"invoke failed; server path retained"); vTaskDelete(nullptr); return;
        }
        ++invocations;
        int64_t elapsed=esp_timer_get_time()-start;
        if(elapsed>max_us) max_us=elapsed;
        if(elapsed>30000) ++deadline_misses;
        float score=(output->data.uint8[0]-output->params.zero_point)*output->params.scale;
        if(score>peak) peak=score;
        bool eligible=seen>=150 && window_eligible && age<100000;
        streak=(eligible && score>=.70f)?streak+1:0;
        window_eligible=true;
        int64_t now=esp_timer_get_time();
        if(streak>=1 && now-last_hit>2000000) {
            ++hits; last_hit=now; streak=0;
            ESP_LOGI(TAG,"CANDIDATE mono_us=%lld score=%.4f queue_us=%lld NO_ACTION",
                (long long)now,(double)score,(long long)age);
        }
        if(now-report_at>=1000000) {
            ESP_LOGI(TAG,"stats invokes=%lu peak=%.4f processing_max_us=%lld queue_max_us=%lld drops=%lu candidates=%lu warm=%d deadline_misses=%lu heap_internal=%u heap_min=%u stack_free_min=%u",
                (unsigned long)invocations,(double)peak,(long long)max_us,(long long)max_queue_us,
                (unsigned long)drops.load(),(unsigned long)hits,seen>=150,(unsigned long)deadline_misses,
                (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
                (unsigned)heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL),
                (unsigned)uxTaskGetStackHighWaterMark(nullptr));
            report_at=now; invocations=0; peak=0; max_us=0; max_queue_us=0;
        }
    }
}
}
esp_err_t hanmir_local_wake_start(void) {
    queue=xQueueCreate(12,sizeof(Block));
    if(!queue) return ESP_ERR_NO_MEM;
    if(xTaskCreatePinnedToCore(task,"tutus_shadow",8192,nullptr,3,nullptr,1)!=pdPASS) {
        vQueueDelete(queue); queue=nullptr; return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}
void hanmir_local_wake_feed(const int16_t *pcm,size_t count,bool eligible) {
    if(!ready.load()) return;
    // One producer: AFE fetch task. Never block microphone capture on inference.
    static Block pending{}; static size_t fill=0; static uint32_t sequence=0;
    if(!fill) pending.eligible=true;
    for(size_t n=0;n<count;++n) {
        pending.eligible=pending.eligible && eligible;
        pending.pcm[fill++]=eligible?pcm[n]:0;
        if(fill==160) {
            pending.seq=++sequence; pending.queued_us=esp_timer_get_time();
            if(xQueueSend(queue,&pending,0)!=pdTRUE) ++drops;
            fill=0; pending.eligible=true;
        }
    }
}
#else
esp_err_t hanmir_local_wake_start(void) { return ESP_OK; }
void hanmir_local_wake_feed(const int16_t *,size_t,bool) {}
#endif
