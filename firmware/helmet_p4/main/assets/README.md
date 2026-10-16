# Wake acknowledgement audio

`wake_ack.pcm`: signed PCM16 little endian, mono, 16000 Hz.
Korean text: 네, 말씀하세요.
Generated using the configured project edge-tts voice on 2026-10-16.
Leading/trailing silence trimmed with 20ms lead and 50ms tail around |sample| > 150.
Contains synthesized fixed text, not a user microphone recording.
Played locally for acknowledgement commands; no TTS download needed on updated firmware.
Wake detection itself remains server STT until a validated Korean keyword model is integrated.
