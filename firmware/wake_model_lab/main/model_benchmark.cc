// Isolated operator/memory benchmark. No microphone, wake detection or networking.
#include <cstring>
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/micro_resource_variable.h"
#include "tensorflow/lite/schema/schema_generated.h"
#include "tutus_frontend.h"
#include "frontend_golden.h"

extern const unsigned char model_data[] asm("_binary_tutus_pilot_tflite_start");
static const char *TAG = "tutus_lab";
extern "C" void app_main() {
    if (!tutus_frontend_init()) { ESP_LOGE(TAG,"frontend init failed"); return; }
    uint32_t checksum=2166136261u;
    int frames=0;
    int64_t frontend_start=esp_timer_get_time();
    for (int n=0;n<50;++n) {
        int16_t pcm[160]; float features[40];
        for(int j=0;j<160;++j) pcm[j]=((n*160+j)*97)%20001-10000;
        if(tutus_frontend_process(pcm,features)) {
            ++frames;
            for(float value:features) {
                uint16_t raw=(uint16_t)(value/.0390625f);
                checksum=(checksum^(raw&255))*16777619u;
                checksum=(checksum^(raw>>8))*16777619u;
            }
        }
    }
    int64_t frontend_us=esp_timer_get_time()-frontend_start;
    tutus_frontend_free();
    ESP_LOGI(TAG,"frontend synthetic frames=%d checksum=%lu expected=%lu total_us=%lld parity=%s",
        frames,(unsigned long)checksum,(unsigned long)FRONTEND_GOLDEN_CHECKSUM,(long long)frontend_us,
        frames==FRONTEND_GOLDEN_FRAMES && checksum==FRONTEND_GOLDEN_CHECKSUM ? "PASS" : "FAIL");
    if(frames!=FRONTEND_GOLDEN_FRAMES || checksum!=FRONTEND_GOLDEN_CHECKSUM) return;
    const auto *model = tflite::GetModel(model_data);
    if (model->version() != TFLITE_SCHEMA_VERSION) {
        ESP_LOGE(TAG, "schema mismatch"); return;
    }
    static tflite::MicroMutableOpResolver<13> ops;
#define ADD_OP(name) if (ops.Add##name() != kTfLiteOk) { ESP_LOGE(TAG, "op registration: " #name); return; }
    ADD_OP(AssignVariable); ADD_OP(CallOnce); ADD_OP(Concatenation);
    ADD_OP(Conv2D); ADD_OP(DepthwiseConv2D); ADD_OP(FullyConnected);
    ADD_OP(Logistic); ADD_OP(Quantize); ADD_OP(ReadVariable);
    ADD_OP(Reshape); ADD_OP(SplitV); ADD_OP(StridedSlice); ADD_OP(VarHandle);
#undef ADD_OP
    constexpr size_t capacity = 128 * 1024;
    auto *arena = static_cast<uint8_t *>(heap_caps_aligned_alloc(16, capacity, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT));
    if (!arena) { ESP_LOGE(TAG, "arena allocation failed"); return; }
    auto *allocator = tflite::MicroAllocator::Create(arena, capacity);
    if (!allocator) { ESP_LOGE(TAG, "allocator creation failed"); return; }
    int handles = 0;
    for (unsigned g = 0; g < model->subgraphs()->size(); ++g) {
        for (const auto *op : *model->subgraphs()->Get(g)->operators()) {
            const auto *code = model->operator_codes()->Get(op->opcode_index());
            if (code->builtin_code() == tflite::BuiltinOperator_VAR_HANDLE) ++handles;
        }
    }
    auto *variables = tflite::MicroResourceVariables::Create(allocator, handles);
    if (!variables) { ESP_LOGE(TAG, "resource allocation failed"); return; }
    tflite::MicroInterpreter interpreter(model, ops, allocator, variables);
    if (interpreter.AllocateTensors() != kTfLiteOk) {
        ESP_LOGE(TAG, "AllocateTensors failed"); return;
    }
    auto *input = interpreter.input(0);
    auto *output = interpreter.output(0);
    if (input->type != kTfLiteInt8 || input->bytes != 120 || output->type != kTfLiteUInt8) {
        ESP_LOGE(TAG, "unexpected model tensor contract"); return;
    }
    ESP_LOGI(TAG, "allocated arena_used=%u capacity=%u resource_handles=%d input_scale=%.9f zero=%ld",
        (unsigned)interpreter.arena_used_bytes(), (unsigned)capacity, handles,
        (double)input->params.scale, (long)input->params.zero_point);
    int64_t sum = 0, maximum = 0;
    int misses = 0;
    // Synthetic zero FEATURES, not microphone silence; no recognition claim.
    memset(input->data.int8, input->params.zero_point, input->bytes);
    for (int n = 0; n < 100; ++n) {
        int64_t start = esp_timer_get_time();
        if (interpreter.Invoke() != kTfLiteOk) { ESP_LOGE(TAG, "Invoke failed step=%d", n); return; }
        int64_t us = esp_timer_get_time() - start;
        sum += us; if (us > maximum) maximum = us;
        if (us > 30000) ++misses;
        vTaskDelay(pdMS_TO_TICKS(30));
    }
    ESP_LOGI(TAG, "SYNTHETIC_ONLY count=100 invoke_mean_us=%lld invoke_max_us=%lld deadline_30ms_misses=%d output=%u heap=%u",
        (long long)(sum/100), (long long)maximum, misses, output->data.uint8[0],
        (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL));
    ESP_LOGW(TAG, "No microphone/keyword-end/ACK timing measured; not a helmet firmware replacement.");
}
