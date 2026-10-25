#include "hanmir.h"
#include "esp_log.h"
#include "cJSON.h"
#include <stdatomic.h>
static const char *TAG = "hanmir_ov5647";
static atomic_bool capturing;
bool hanmir_camera_source_ready(void) { return atomic_load(&capturing); }

#if CONFIG_HANMIR_ENABLE_CAMERA
#include <fcntl.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include "esp_video_init.h"
#include "esp_video_ioctl.h"
#include "esp_timer.h"
#include "esp_heap_caps.h"
#include <errno.h>
#include "esp_video_device.h"
#include "linux/videodev2.h"
#include "driver/jpeg_encode.h"
#include <stdatomic.h>

static atomic_int target_fps = CONFIG_HANMIR_CAMERA_TARGET_FPS;
static atomic_uint encode_skipped;
int hanmir_camera_target_fps(void) { return atomic_load(&target_fps); }
uint32_t hanmir_camera_encode_skipped(void) { return atomic_load(&encode_skipped); }
bool hanmir_camera_set_target_fps(int fps)
{
    if (fps < 10 || fps > 30) return false;
    atomic_store(&target_fps, fps);
    return true;
}
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static int camera_fd = -1;
static uint8_t *buffers[2];
static size_t buffer_sizes[2];
static uint8_t *jpeg_buffer;
static size_t jpeg_capacity;
static jpeg_encoder_handle_t encoder;
static jpeg_encode_cfg_t encoding;
static const uint32_t video_flags = ESP_VIDEO_INIT_FLAGS_MIPI_CSI | ESP_VIDEO_INIT_FLAGS_ISP;
static atomic_bool manager_started, restart_requested;
static atomic_uint init_attempts, failures, full_recoveries, stream_recoveries, total_frames;
static atomic_uint last_frame_ms, retry_ms, camera_stack_min;
static atomic_int last_error, last_errno;
static _Atomic(const char *) stage = "idle", failure_stage = "none";

static void camera_failure(const char *where, esp_err_t error, int system_error)
{
    atomic_store(&failure_stage, where);
    atomic_store(&last_error, error);
    atomic_store(&last_errno, system_error);
    atomic_fetch_add(&failures, 1);
    ESP_LOGE(TAG, "camera fault stage=%s error=%s errno=%d attempt=%u heap=%u largest=%u psram=%u",
        where, esp_err_to_name(error), system_error, atomic_load(&init_attempts),
        (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
        (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
        (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
}

void hanmir_camera_source_diagnostics(cJSON *object)
{
    if (!object) return;
    cJSON_AddStringToObject(object, "stage", atomic_load(&stage));
    cJSON_AddStringToObject(object, "last_failure_stage", atomic_load(&failure_stage));
    cJSON_AddStringToObject(object, "last_error", esp_err_to_name(atomic_load(&last_error)));
    cJSON_AddNumberToObject(object, "last_errno", atomic_load(&last_errno));
    cJSON_AddNumberToObject(object, "init_attempts", atomic_load(&init_attempts));
    cJSON_AddNumberToObject(object, "failures", atomic_load(&failures));
    cJSON_AddNumberToObject(object, "recoveries", atomic_load(&full_recoveries));
    cJSON_AddNumberToObject(object, "stream_recoveries", atomic_load(&stream_recoveries));
    unsigned frames = atomic_load(&total_frames);
    cJSON_AddNumberToObject(object, "frames", frames);
    if (frames) cJSON_AddNumberToObject(object, "frame_age_ms",
        (uint32_t)(esp_timer_get_time() / 1000) - atomic_load(&last_frame_ms));
    else cJSON_AddNullToObject(object, "frame_age_ms");
    cJSON_AddNumberToObject(object, "retry_ms", atomic_load(&retry_ms));
    cJSON_AddNumberToObject(object, "stack_min", atomic_load(&camera_stack_min));
}

bool hanmir_camera_source_restart(void)
{
    if (!atomic_load(&manager_started)) return false;
    // Only the camera owner touches its resources; socket callbacks just request.
    atomic_store(&restart_requested, true);
    return true;
}


static void release_camera(void)
{
    atomic_store(&capturing, false);
    if (camera_fd >= 0) {
        int type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        ioctl(camera_fd, VIDIOC_STREAMOFF, &type);
        for (int i = 0; i < 2; i++) {
            if (buffers[i] && buffers[i] != MAP_FAILED) {
                munmap(buffers[i], buffer_sizes[i]);
                buffers[i] = NULL;
            }
        }
        close(camera_fd);
        camera_fd = -1;
    }
    if (encoder) { jpeg_del_encoder_engine(encoder); encoder = NULL; }
    free(jpeg_buffer);
    jpeg_buffer = NULL;
    jpeg_capacity = 0;
}

static bool deinit_video(void)
{
    atomic_store(&stage, "video_deinit");
    esp_err_t err = esp_video_deinit_with_flags(video_flags);
    if (err != ESP_OK) camera_failure("video_deinit", err, 0);
    return err == ESP_OK;
}

static void capture_loop(void)
{
    unsigned frames = 0, recoveries = 0, consecutive_dq = 0, consecutive_encode = 0;
    int64_t logged = esp_timer_get_time();
    int64_t next_encode = 0;
    uint32_t max_dq_ms = 0, max_encode_ms = 0;
    for (;;) {
        atomic_store(&camera_stack_min, uxTaskGetStackHighWaterMark(NULL));
        if (atomic_exchange(&restart_requested, false)) {
            ESP_LOGW(TAG, "camera-only restart requested; other modules remain active");
            return;
        }
        struct v4l2_buffer frame = {.type = V4L2_BUF_TYPE_VIDEO_CAPTURE,
                                  .memory = V4L2_MEMORY_MMAP};
        int64_t begin = esp_timer_get_time();
        if (ioctl(camera_fd, VIDIOC_DQBUF, &frame) != 0) {
            camera_failure("dequeue", ESP_FAIL, errno);
            if (++consecutive_dq >= 3) return;
            ESP_LOGW(TAG, "stream recovery=%u consecutive_dq=%u", ++recoveries, consecutive_dq);
            int type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
            if (ioctl(camera_fd, VIDIOC_STREAMOFF, &type) != 0) { camera_failure("streamoff", ESP_FAIL, errno); return; }
            bool queued = true;
            for (unsigned i = 0; i < 2; ++i) {
                struct v4l2_buffer buf = {.index=i, .type=V4L2_BUF_TYPE_VIDEO_CAPTURE,
                                         .memory=V4L2_MEMORY_MMAP};
                if (ioctl(camera_fd, VIDIOC_QBUF, &buf) != 0) queued = false;
            }
            if (!queued) { camera_failure("requeue", ESP_FAIL, errno); return; }
            if (ioctl(camera_fd, VIDIOC_STREAMON, &type) != 0) { camera_failure("streamon", ESP_FAIL, errno); return; }
            atomic_fetch_add(&stream_recoveries, 1);
            ESP_LOGW(TAG, "camera stream recovered; settings retained");
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }
        consecutive_dq = 0;
        uint32_t dq_ms = (esp_timer_get_time() - begin) / 1000;
        if (dq_ms > max_dq_ms) max_dq_ms = dq_ms;
        bool encode_due = esp_timer_get_time() >= next_encode && hanmir_camera_can_encode();
        if (frame.index < 2 && (frame.flags & V4L2_BUF_FLAG_DONE) && encode_due) {
            next_encode = esp_timer_get_time() + 1000000 / hanmir_camera_target_fps();
            uint32_t size = 0;
            begin = esp_timer_get_time();
            esp_err_t err = jpeg_encoder_process(encoder, &encoding,
                buffers[frame.index], frame.bytesused,
                jpeg_buffer, jpeg_capacity, &size);
            uint32_t encode_ms = (esp_timer_get_time() - begin) / 1000;
            if (encode_ms > max_encode_ms) max_encode_ms = encode_ms;
            if (err == ESP_OK) {
                consecutive_encode = 0;
                atomic_fetch_add(&total_frames, 1);
                atomic_store(&last_frame_ms, (uint32_t)(esp_timer_get_time() / 1000));
                hanmir_camera_submit_jpeg(jpeg_buffer, size, encoding.width, encoding.height);
                if (++frames % 100 == 0) ESP_LOGI(TAG, "captured %u JPEG frames; transport drops=%lu", frames, (unsigned long)hanmir_camera_dropped());
            } else {
                camera_failure("jpeg_encode", err, 0);
                if (++consecutive_encode >= 3) return;
            }
        } else atomic_fetch_add(&encode_skipped, 1);
        if (ioctl(camera_fd, VIDIOC_QBUF, &frame) != 0) { camera_failure("qbuf", ESP_FAIL, errno); return; }
        if (esp_timer_get_time() - logged > 5000000) {
            ESP_LOGI(TAG, "capture stats frames=%u dq_max_ms=%lu encode_max_ms=%lu recoveries=%u stack_free=%u",
                     frames, (unsigned long)max_dq_ms, (unsigned long)max_encode_ms, recoveries,
                     (unsigned)uxTaskGetStackHighWaterMark(NULL));
            max_dq_ms = max_encode_ms = 0; logged = esp_timer_get_time();
        }
        // Do not add a full frame period AFTER capture/encode time, and round
        // waits up to RTOS ticks instead of accidentally exceeding the FPS cap.
        int64_t remaining_us = next_encode - esp_timer_get_time();
        uint32_t wait_ms = remaining_us > 0 ? (uint32_t)((remaining_us + 999) / 1000) : 1;
        TickType_t wait_ticks = (wait_ms + portTICK_PERIOD_MS - 1) / portTICK_PERIOD_MS;
        vTaskDelay(wait_ticks ? wait_ticks : 1);
    }
}

static esp_err_t initialize_camera(void)
{
    atomic_fetch_add(&init_attempts, 1);
    atomic_store(&stage, "sensor_detect");
    errno = 0;
    const esp_video_init_csi_config_t csi = {
        .sccb_config = {.init_sccb = true,
            .i2c_config = {.port = 0, .sda_pin = CONFIG_HANMIR_CAMERA_SDA_GPIO,
                          .scl_pin = CONFIG_HANMIR_CAMERA_SCL_GPIO}, .freq = 100000},
        .reset_pin = -1, .pwdn_pin = -1,
    };
    const esp_video_init_config_t video = {.csi = &csi};
    esp_err_t err = esp_video_init_with_flags(&video,
        video_flags);
    if (err != ESP_OK) { camera_failure("sensor_detect", err, errno); return err; }
    err = ESP_FAIL;
    atomic_store(&stage, "device_open");
    errno = 0;
    camera_fd = open(ESP_VIDEO_MIPI_CSI_DEVICE_NAME, O_RDWR);
    if (camera_fd < 0) { camera_failure("device_open", ESP_FAIL, errno); return ESP_FAIL; }
    atomic_store(&stage, "dq_timeout");
    struct timeval dq_timeout = {.tv_sec = 2};
    if (ioctl(camera_fd, VIDIOC_S_DQBUF_TIMEOUT, &dq_timeout) != 0) goto failed;
    atomic_store(&stage, "format");
    struct v4l2_format format = {.type = V4L2_BUF_TYPE_VIDEO_CAPTURE};
    if (ioctl(camera_fd, VIDIOC_G_FMT, &format) != 0) goto failed;
    format.fmt.pix.pixelformat = V4L2_PIX_FMT_RGB565;
    if (ioctl(camera_fd, VIDIOC_S_FMT, &format) != 0) goto failed;
    encoding = (jpeg_encode_cfg_t){.width = format.fmt.pix.width,
        .height = format.fmt.pix.height, .src_type = JPEG_ENCODE_IN_FORMAT_RGB565,
        .sub_sample = JPEG_DOWN_SAMPLING_YUV422,
        .image_quality = CONFIG_HANMIR_CAMERA_JPEG_QUALITY};
    atomic_store(&stage, "jpeg_engine");
    jpeg_encode_engine_cfg_t engine = {.timeout_ms = 1000};
    err = jpeg_new_encoder_engine(&engine, &encoder);
    if (err != ESP_OK) goto failed;
    err = ESP_FAIL;
    atomic_store(&stage, "jpeg_buffer");
    jpeg_encode_memory_alloc_cfg_t mem = {.buffer_direction = JPEG_ENC_ALLOC_OUTPUT_BUFFER};
    jpeg_buffer = jpeg_alloc_encoder_mem(CONFIG_HANMIR_CAMERA_MAX_BYTES, &mem, &jpeg_capacity);
    if (!jpeg_buffer) { err = ESP_ERR_NO_MEM; goto failed; }
    atomic_store(&stage, "capture_buffers");
    struct v4l2_requestbuffers req = {.count = 2,
        .type = V4L2_BUF_TYPE_VIDEO_CAPTURE, .memory = V4L2_MEMORY_MMAP};
    if (ioctl(camera_fd, VIDIOC_REQBUFS, &req) != 0 || req.count < 2) goto failed;
    for (int i = 0; i < 2; i++) {
        struct v4l2_buffer buf = {.index = i,
            .type = V4L2_BUF_TYPE_VIDEO_CAPTURE, .memory = V4L2_MEMORY_MMAP};
        if (ioctl(camera_fd, VIDIOC_QUERYBUF, &buf) != 0) goto failed;
        buffer_sizes[i] = buf.length;
        buffers[i] = mmap(NULL, buf.length, PROT_READ | PROT_WRITE, MAP_SHARED, camera_fd, buf.m.offset);
        if (!buffers[i] || buffers[i] == MAP_FAILED || ioctl(camera_fd, VIDIOC_QBUF, &buf) != 0) goto failed;
    }
    int type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    atomic_store(&stage, "streamon");
    if (ioctl(camera_fd, VIDIOC_STREAMON, &type) != 0) goto failed;
    atomic_store(&capturing, true);
    atomic_store(&stage, "capturing");
    ESP_LOGI(TAG, "OV5647 started: %lux%lu, quality=%d, target=%d FPS",
        (unsigned long)encoding.width, (unsigned long)encoding.height,
        CONFIG_HANMIR_CAMERA_JPEG_QUALITY, CONFIG_HANMIR_CAMERA_TARGET_FPS);
    return ESP_OK;
failed:
    camera_failure(atomic_load(&stage), err, errno);
    return err;
}

static void camera_supervisor(void *arg)
{
    unsigned backoff = 5000;
    bool clean = atomic_load(&capturing) || deinit_video();
    for (;;) {
        if (atomic_load(&capturing)) {
            uint32_t before = atomic_load(&total_frames);
            capture_loop();
            // Backoff resets only after actual good frames, never just STREAMON.
            if (atomic_load(&total_frames) - before >= 30) backoff = 5000;
            release_camera();
            clean = deinit_video();
        }
        atomic_store(&stage, "retry_wait");
        atomic_store(&retry_ms, backoff);
        ESP_LOGW(TAG, "camera-only retry in %u ms; failures=%u frames=%u", backoff,
                 atomic_load(&failures), atomic_load(&total_frames));
        // Poll a manual request without keeping the CPU busy during backoff.
        for (unsigned waited = 0; waited < backoff; waited += 100) {
            vTaskDelay(pdMS_TO_TICKS(100));
            if (atomic_exchange(&restart_requested, false)) break;
        }
        atomic_store(&retry_ms, 0);
        atomic_store(&camera_stack_min, uxTaskGetStackHighWaterMark(NULL));
        if (!clean) clean = deinit_video();
        if (clean && initialize_camera() == ESP_OK) {
            atomic_fetch_add(&full_recoveries, 1);
            ESP_LOGI(TAG, "camera-only reinitialization complete count=%u", atomic_load(&full_recoveries));
        } else {
            release_camera();
            clean = deinit_video();
            if (backoff < 30000) backoff = backoff * 2 > 30000 ? 30000 : backoff * 2;
        }
    }
}

esp_err_t hanmir_camera_source_start(void)
{
    if (atomic_exchange(&manager_started, true)) return ESP_ERR_INVALID_STATE;
    // Preserve the original startup ordering before microphone/speaker allocation.
    bool ready = initialize_camera() == ESP_OK;
    if (!ready) { release_camera(); deinit_video(); }
    if (xTaskCreate(camera_supervisor, "camera_capture", 8192, NULL, 3, NULL) != pdPASS) {
        camera_failure("supervisor_task", ESP_ERR_NO_MEM, 0);
        release_camera(); deinit_video();
        atomic_store(&manager_started, false);
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}
#else
void hanmir_camera_source_diagnostics(cJSON *object) {
    if (object) cJSON_AddStringToObject(object, "stage", "disabled");
}
bool hanmir_camera_source_restart(void) { return false; }
int hanmir_camera_target_fps(void) { return 0; }
uint32_t hanmir_camera_encode_skipped(void) { return 0; }
bool hanmir_camera_set_target_fps(int fps) { (void)fps; return false; }
esp_err_t hanmir_camera_source_start(void)
{
    ESP_LOGW(TAG, "Camera disabled in HANMIR configuration");
    return ESP_ERR_NOT_SUPPORTED;
}
#endif
