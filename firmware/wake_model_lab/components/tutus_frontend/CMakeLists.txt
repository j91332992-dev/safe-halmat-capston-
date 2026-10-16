set(base "vendor/tensorflow/lite/experimental/microfrontend/lib")
set(files kiss_fft_int16.cc fft.cc fft_util.cc filterbank.cc filterbank_util.cc
    frontend.cc frontend_util.cc log_lut.cc log_scale.cc log_scale_util.cc
    noise_reduction.cc noise_reduction_util.cc pcan_gain_control.cc
    pcan_gain_control_util.cc window.cc window_util.cc)
set(src tutus_frontend.cc)
foreach(f ${files})
    list(APPEND src "${base}/${f}")
endforeach()
list(APPEND src vendor/kissfft/kiss_fft.cc vendor/kissfft/tools/kiss_fftr.cc)
idf_component_register(SRCS ${src} INCLUDE_DIRS "." PRIV_INCLUDE_DIRS vendor vendor/kissfft)
target_compile_definitions(${COMPONENT_LIB} PRIVATE FIXED_POINT=16)
