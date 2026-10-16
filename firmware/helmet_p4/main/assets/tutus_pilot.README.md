# Experimental Tutus v2 model

SHA256: 42709ab464158d10ef48083269af60e06c1a9a433c946c46de9facb0d83c471d
29,336 bytes. Trained locally from human-labeled user recordings using micro-wake-word MixedNet.
See docs/TUTUS_PILOT_TRAINING_2026-10-16.md for provenance and failed/limited validation.

Only linked with CONFIG_HANMIR_LOCAL_WAKE_SHADOW=y. Default disabled.
Runtime logs scores/candidates; does not acknowledge, call an API, suppress server wake,
or remove wake-free emergency STT. No claim of 500ms end-to-end performance.
Observation rule .70 for 1 output is experimental, not an approved operating threshold.
Offline pilot scores did not remain above .70 for 3 consecutive outputs in any positive clip;
single-output events are logged for analysis only and must not directly trigger playback.
After startup or dropped PCM blocks, 1.5 seconds of input is required before candidate logs.
Playback/call audio is replaced with zeros and candidates suppressed for affected windows.
Do not promote this pilot to a safety-related production detector without independent testing.
