#include "hanmir.h"
#include "esp_log.h"
static const char *TAG = "hanmir_ov5647";
static volatile bool capturing;
bool hanmir_camera_source_ready(void) { return capturing; }

#if CONFIG_HANMIR_ENABLE_CAMERA
#include <fcntl.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include "esp_video_init.h"
#include "esp_video_ioctl.h"
#include "esp_timer.h"
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

static void release_camera(void)
{
    capturing = false;
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
}

static void capture_task(void *arg)
{
    unsigned frames = 0, recoveries = 0;
    int64_t logged = esp_timer_get_time();
    int64_t next_encode = 0;
    uint32_t max_dq_ms = 0, max_encode_ms = 0;
    for (;;) {
        struct v4l2_buffer frame = {.type = V4L2_BUF_TYPE_VIDEO_CAPTURE,
                                  .memory = V4L2_MEMORY_MMAP};
        int64_t begin = esp_timer_get_time();
        if (ioctl(camera_fd, VIDIOC_DQBUF, &frame) != 0) {
            ESP_LOGE(TAG, "camera dequeue timeout/error errno=%d; stream recovery=%u", errno, ++recoveries);
            int type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
            if (ioctl(camera_fd, VIDIOC_STREAMOFF, &type) != 0) break;
            bool queued = true;
            for (unsigned i = 0; i < 2; ++i) {
                struct v4l2_buffer buf = {.index=i, .type=V4L2_BUF_TYPE_VIDEO_CAPTURE,
                                         .memory=V4L2_MEMORY_MMAP};
                if (ioctl(camera_fd, VIDIOC_QBUF, &buf) != 0) queued = false;
            }
            if (!queued || ioctl(camera_fd, VIDIOC_STREAMON, &type) != 0) break;
            ESP_LOGW(TAG, "camera stream recovered; settings retained");
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }
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
                hanmir_camera_submit_jpeg(jpeg_buffer, size, encoding.width, encoding.height);
                if (++frames % 100 == 0) ESP_LOGI(TAG, "captured %u JPEG frames; transport drops=%lu", frames, (unsigned long)hanmir_camera_dropped());
            } else ESP_LOGW(TAG, "JPEG encoding: %s", esp_err_to_name(err));
        } else atomic_fetch_add(&encode_skipped, 1);
        if (ioctl(camera_fd, VIDIOC_QBUF, &frame) != 0) break;
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
    release_camera();
    vTaskDelete(NULL);
}

esp_err_t hanmir_camera_source_start(void)
{
    const esp_video_init_csi_config_t csi = {
        .sccb_config = {.init_sccb = true,
            .i2c_config = {.port = 0, .sda_pin = CONFIG_HANMIR_CAMERA_SDA_GPIO,
                          .scl_pin = CONFIG_HANMIR_CAMERA_SCL_GPIO}, .freq = 100000},
        .reset_pin = -1, .pwdn_pin = -1,
    };
    const esp_video_init_config_t video = {.csi = &csi};
    esp_err_t err = esp_video_init_with_flags(&video,
        ESP_VIDEO_INIT_FLAGS_MIPI_CSI | ESP_VIDEO_INIT_FLAGS_ISP);
    if (err != ESP_OK) return err;
    camera_fd = open(ESP_VIDEO_MIPI_CSI_DEVICE_NAME, O_RDWR);
    if (camera_fd < 0) return ESP_FAIL;
    struct timeval dq_timeout = {.tv_sec = 2};
    if (ioctl(camera_fd, VIDIOC_S_DQBUF_TIMEOUT, &dq_timeout) != 0) goto failed;
    struct v4l2_format format = {.type = V4L2_BUF_TYPE_VIDEO_CAPTURE};
    if (ioctl(camera_fd, VIDIOC_G_FMT, &format) != 0) goto failed;
    format.fmt.pix.pixelformat = V4L2_PIX_FMT_RGB565;
    if (ioctl(camera_fd, VIDIOC_S_FMT, &format) != 0) goto failed;
    encoding = (jpeg_encode_cfg_t){.width = format.fmt.pix.width,
        .height = format.fmt.pix.height, .src_type = JPEG_ENCODE_IN_FORMAT_RGB565,
        .sub_sample = JPEG_DOWN_SAMPLING_YUV422,
        .image_quality = CONFIG_HANMIR_CAMERA_JPEG_QUALITY};
    jpeg_encode_engine_cfg_t engine = {.timeout_ms = 1000};
    if (jpeg_new_encoder_engine(&engine, &encoder) != ESP_OK) goto failed;
    jpeg_encode_memory_alloc_cfg_t mem = {.buffer_direction = JPEG_ENC_ALLOC_OUTPUT_BUFFER};
    jpeg_buffer = jpeg_alloc_encoder_mem(CONFIG_HANMIR_CAMERA_MAX_BYTES, &mem, &jpeg_capacity);
    if (!jpeg_buffer) goto failed;
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
    if (ioctl(camera_fd, VIDIOC_STREAMON, &type) != 0) goto failed;
    if (xTaskCreate(capture_task, "camera_capture", 8192, NULL, 3, NULL) != pdPASS) goto failed;
    capturing = true;
    ESP_LOGI(TAG, "OV5647 started: %lux%lu, quality=%d, target=%d FPS",
        (unsigned long)encoding.width, (unsigned long)encoding.height,
        CONFIG_HANMIR_CAMERA_JPEG_QUALITY, CONFIG_HANMIR_CAMERA_TARGET_FPS);
    return ESP_OK;
failed:
    release_camera();
    return ESP_FAIL;
}
#else
int hanmir_camera_target_fps(void) { return 0; }
uint32_t hanmir_camera_encode_skipped(void) { return 0; }
bool hanmir_camera_set_target_fps(int fps) { (void)fps; return false; }
esp_err_t hanmir_camera_source_start(void)
{
    ESP_LOGW(TAG, "Camera disabled in HANMIR configuration");
    return ESP_ERR_NOT_SUPPORTED;
}
#endif
