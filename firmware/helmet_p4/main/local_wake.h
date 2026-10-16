#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
#ifdef __cplusplus
extern "C" {
#endif
esp_err_t hanmir_local_wake_start(void);
void hanmir_local_wake_feed(const int16_t *pcm, size_t count, bool eligible);
#ifdef __cplusplus
}
#endif
