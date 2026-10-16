#include "tutus_frontend.h"
#include <cstring>
extern "C" {
#include "tensorflow/lite/experimental/microfrontend/lib/frontend.h"
#include "tensorflow/lite/experimental/microfrontend/lib/frontend_util.h"
}
static FrontendState state;
static bool ready;
bool tutus_frontend_init(void) {
    tutus_frontend_free();
    FrontendConfig cfg{};
    cfg.window.size_ms=30; cfg.window.step_size_ms=10;
    cfg.filterbank.num_channels=40;
    cfg.filterbank.lower_band_limit=125; cfg.filterbank.upper_band_limit=7500;
    cfg.noise_reduction.smoothing_bits=10;
    cfg.noise_reduction.even_smoothing=.025f; cfg.noise_reduction.odd_smoothing=.06f;
    cfg.noise_reduction.min_signal_remaining=.05f;
    cfg.pcan_gain_control.enable_pcan=1; cfg.pcan_gain_control.strength=.95f;
    cfg.pcan_gain_control.offset=80; cfg.pcan_gain_control.gain_bits=21;
    cfg.log_scale.enable_log=1; cfg.log_scale.scale_shift=6;
    ready=FrontendPopulateState(&cfg,&state,16000)!=0;
    if (!ready) { FrontendFreeStateContents(&state); memset(&state,0,sizeof(state)); }
    return ready;
}
bool tutus_frontend_process(const int16_t samples[160], float features[40]) {
    if (!ready) return false;
    size_t read=0;
    auto out=FrontendProcessSamples(&state,samples,160,&read);
    if(read!=160 || out.size!=40) return false;
    for(int j=0;j<40;++j) features[j]=out.values[j]*.0390625f;
    return true;
}
void tutus_frontend_free(void) {
    if(ready) FrontendFreeStateContents(&state);
    memset(&state,0,sizeof(state)); ready=false;
}
