#pragma once
#include <stdint.h>
#include <stdbool.h>
#ifdef __cplusplus
extern "C" {
#endif
// Single inference-task owner, 160 mono PCM16 samples each call.
bool tutus_frontend_init(void);
bool tutus_frontend_process(const int16_t samples[160], float features[40]);
void tutus_frontend_free(void);
#ifdef __cplusplus
}
#endif
