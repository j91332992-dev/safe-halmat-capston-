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
#include "esp_video_device.h"
#include "linux/videodev2.h"
#include "driver/jpeg_encode.h"
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
    unsigned frames = 0;
    for (;;) {
        struct v4l2_buffer frame = {.type = V4L2_BUF_TYPE_VIDEO_CAPTURE,
                                  .memory = V4L2_MEMORY_MMAP};
        if (ioctl(camera_fd, VIDIOC_DQBUF, &frame) != 0) {
            ESP_LOGE(TAG, "camera dequeue failed; capture stopped");
            break;
        }
        if (frame.index < 2 && (frame.flags & V4L2_BUF_FLAG_DONE)) {
            uint32_t size = 0;
            esp_err_t err = jpeg_encoder_process(encoder, &encoding,
                buffers[frame.index], frame.bytesused,
                jpeg_buffer, jpeg_capacity, &size);
            if (err == ESP_OK) {
                hanmir_camera_submit_jpeg(jpeg_buffer, size, encoding.width, encoding.height);
                if (++frames % 100 == 0) ESP_LOGI(TAG, "captured %u JPEG frames; transport drops=%lu", frames, (unsigned long)hanmir_camera_dropped());
            } else ESP_LOGW(TAG, "JPEG encoding: %s", esp_err_to_name(err));
        }
        if (ioctl(camera_fd, VIDIOC_QBUF, &frame) != 0) break;
        vTaskDelay(pdMS_TO_TICKS(1000 / CONFIG_HANMIR_CAMERA_TARGET_FPS));
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
esp_err_t hanmir_camera_source_start(void)
{
    ESP_LOGW(TAG, "Camera disabled in HANMIR configuration");
    return ESP_ERR_NOT_SUPPORTED;
}
#endif
