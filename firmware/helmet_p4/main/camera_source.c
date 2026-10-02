#include "hanmir.h"
#include "esp_log.h"

static const char *TAG = "hanmir_ov5647";

esp_err_t hanmir_camera_source_start(void)
{
    /* Hardware gate: DFR1172 OV5647 MIPI CSI/ISP/JPEG requires the verified
     * esp_video board configuration and real camera module. Do not reuse the
     * S3 DVP GPIO map. Once a complete JPEG is available, pass it through
     * hanmir_camera_submit_jpeg(jpeg, len, width, height). That function
     * copies into a latest-only slot so capture never waits on Wi-Fi/YOLO.
     * See README's camera bring-up checklist and official capture_stream.
     */
    ESP_LOGW(TAG, "OV5647 MIPI CSI/ISP integration awaits DFR1172 board validation");
    return ESP_ERR_NOT_SUPPORTED;
}
