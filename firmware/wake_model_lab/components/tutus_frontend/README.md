# Training-compatible frontend

Vendored from https://github.com/rhasspy/pymicro-features at
`96bd69cfad79aa67697e176570d3dd87052c3def`, package version 2.0.2.
Apache license and source copyright notices retained in vendor/; KissFFT notices retained in its source files.
Source folders copied unchanged. CMake explicitly compiles library sources, not upstream tests/tools.
The wrapper mirrors src/micro_features.cpp settings and output scaling exactly.
16kHz mono PCM16, 30ms window, 10ms step, 40 channels. Stateful, single task owner.
This does not reuse ESP-SR feature vectors. P4 numerical parity still requires on-device validation.
