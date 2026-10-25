from pathlib import Path
import hashlib
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    audio_lossless_transport_enabled: bool = False
    app_name: str = "ESP32 스마트 안전관제 서버"
    api_prefix: str = "/api"
    database_url: str = f"sqlite:///{(BASE_DIR / 'safety.db').as_posix()}"
    operation_mode: str = "hardware"
    site_id: str = "site-001"
    site_name: str = "한미르 UWB 테스트 공간"
    site_width_m: float = 5.8
    site_height_m: float = 8.2
    device_offline_seconds: int = 20
    location_ema_alpha: float = 0.65
    uwb_log_path: str = str(BASE_DIR / "logs" / "uwb-observations.jsonl")
    uwb_log_max_bytes: int = 10 * 1024 * 1024
    uwb_log_backups: int = 4
    uwb_log_retention_days: float = 7
    uwb_calibration_enabled: bool = False
    uwb_median_enabled: bool = True
    uwb_median_window: int = Field(default=5, ge=1, le=101)
    uwb_median_sample_ttl_seconds: float = Field(default=3.0, gt=0)
    uwb_filter_reset_seconds: float = Field(default=15.0, gt=0)
    uwb_frame_max_age_seconds: float = Field(default=5.0, gt=0)
    uwb_filter_state_ttl_seconds: float = Field(default=3600, ge=60)
    uwb_filter_max_tags: int = Field(default=1000, ge=1, le=100000)
    uwb_filter_state_path: str = str(BASE_DIR / "logs" / "uwb-distance-state.sqlite3")
    # Trial assumptions, not validated human-motion or safety limits.
    uwb_speed_mode: Literal["observe", "enforce"] = "observe"
    uwb_max_speed_mps: float = Field(default=3.0, gt=0, allow_inf_nan=False)
    uwb_speed_margin_m: float = Field(default=1.0, ge=0, allow_inf_nan=False)
    uwb_speed_min_dt_seconds: float = Field(default=0.02, gt=0)
    uwb_speed_max_gap_seconds: float = Field(default=10.0, gt=0)
    uwb_speed_acquire_samples: int = Field(default=3, ge=2, le=100)
    uwb_speed_acquire_span_seconds: float = Field(default=0.6, gt=0)
    uwb_speed_acquire_margin_m: float = Field(default=0.75, ge=0)
    uwb_speed_reacquire_rejections: int = Field(default=5, ge=2)
    uwb_speed_reacquire_span_seconds: float = Field(default=2.0, gt=0)
    uwb_speed_state_ttl_seconds: float = Field(default=3600, ge=60)
    # Provisional Ipatov rules; no labelled LOS/NLOS calibration dataset yet.
    uwb_quality_mode: Literal["observe", "weighted", "enforce"] = "observe"
    uwb_quality_nlos_weight: float = Field(default=0.15, ge=0.05, le=1)
    uwb_quality_weight_recovery_step: float = Field(default=0.10, gt=0, le=1)
    uwb_jump_mode: Literal["observe", "enforce"] = "enforce"
    uwb_jump_speed_mps: float = Field(default=3.0, gt=0, le=20)
    uwb_jump_margin_m: float = Field(default=0.20, ge=0, le=2)
    uwb_jump_max_step_m: float = Field(default=0.60, gt=0, le=5)
    uwb_jump_confirm_samples: int = Field(default=3, ge=2, le=20)
    uwb_jump_confirm_seconds: float = Field(default=0.30, gt=0, le=5)
    uwb_jump_reset_gap_seconds: float = Field(default=1.0, gt=0, le=30)
    uwb_location_failure_notice_seconds: float = Field(default=600.0, ge=1, allow_inf_nan=False)
    uwb_survey_device_token: str | None = None
    uwb_survey_site_id: str = "site-001"
    uwb_quality_gap_warn_db: float = Field(default=6, ge=0, allow_inf_nan=False)
    uwb_quality_gap_bad_db: float = Field(default=12, ge=0, allow_inf_nan=False)
    uwb_quality_path_warn_samples: float = Field(default=4, ge=0, allow_inf_nan=False)
    uwb_quality_path_bad_samples: float = Field(default=10, ge=0, allow_inf_nan=False)
    uwb_quality_rx_weak_dbm: float = Field(default=-90, allow_inf_nan=False)
    uwb_quality_fp_weak_dbm: float = Field(default=-95, allow_inf_nan=False)
    uwb_quality_gap_tolerance_db: float = Field(default=0.5, ge=0, allow_inf_nan=False)
    uwb_quality_suspect_weight: float = Field(default=0.35, ge=0.05, lt=1)
    uwb_quality_unknown_weight: float = Field(default=0.2, ge=0.05, lt=1)
    uwb_quality_unknown_policy: Literal["downweight", "exclude"] = "downweight"
    uwb_quality_recovery_samples: int = Field(default=3, ge=2, le=100)
    uwb_quality_recovery_span_seconds: float = Field(default=0.6, gt=0)
    uwb_solver_min_geometry_ratio: float = Field(default=1e-6, gt=0, lt=0.25)
    uwb_solver_max_rmse_m: float = Field(default=1.0, gt=0, allow_inf_nan=False)
    location_stationary_radius_m: float = 0.15
    # Keep receiving positions continuously, but leave a stationary marker fixed
    # until movement from the last accepted position reaches 30 cm consistently three times.
    location_move_start_m: float = 0.30
    location_move_confirm_samples: int = 3
    location_stop_window_seconds: float = 0.8
    location_stop_spread_m: float = 0.30
    location_stop_net_m: float = 0.04
    # Legacy settings retained for compatibility; timed window replaces them.
    location_stop_step_m: float = 0.08
    location_stop_confirm_samples: int = 3
    # Browser development plus native Capacitor Android/iOS WebViews.
    # Android uses https://localhost when androidScheme is set to https.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost,https://localhost,capacitor://localhost,ionic://localhost"
    openai_api_key: str | None = None
    use_whisper_stt: bool = True
    call_voice_end_enabled: bool = True
    call_voice_end_rms: float = Field(default=120.0, ge=1, le=32767)
    tts_timeout_seconds: float = Field(default=8.0, gt=0, le=60)
    voice_trace_enabled: bool = True
    voice_trace_retain_audio: bool = False
    voice_trace_audio_files: int = Field(default=12, ge=1, le=100)
    voice_trace_max_bytes: int = Field(default=5 * 1024 * 1024, ge=1024)
    voice_trace_backups: int = Field(default=3, ge=0, le=100)
    voice_trace_retention_days: float = Field(default=7, gt=0)
    stt_model: str = "gpt-4o-mini-transcribe"
    stt_language: str = "ko"
    stt_prompt: str = "한국어 산업 안전 현장 대화입니다. 호출어 투투스와 작업자의 짧은 명령을 정확히 받아쓰고, 들리지 않는 내용은 추측하지 마세요."
    stt_command_prompt: str = "한국어 산업 안전 현장 대화입니다. 작업자의 짧은 명령을 정확히 받아쓰고, 들리지 않는 내용은 추측하지 마세요."
    stt_timeout_seconds: float = 10.0
    # 짧은 호출어는 STT에서 받침/띄어쓰기 차이가 자주 난다. 자주 쓰는
    # 전사 변형을 명시하고, 단어 전체가 아닌 일상 대화에 오작동하지 않는
    # 수준으로 유사도 임계값을 조금 완화한다.
    wake_word_aliases: str = "투투스,투투,투투 쓰,투투즈,투투스야,투투야,두두스,두두"
    wake_word_fuzzy_threshold: float = 65.0
    # 서버는 호출어를 먼저 받고, 안전모는 안내음을 끝까지 재생한 뒤 녹음을
    # 재개한다. STT 전송 시간까지 고려해 서버 쪽 세션은 더 길게 유지한다.
    # 호출어 → 안내음 재생 → 후속 음성 녹음 → STT 업로드 시간을 고려해
    # 안전모의 8초 대기보다 길게 유지한다.
    wake_followup_seconds: float = 20.0
    voice_command_cooldown_seconds: float = 3.0
    use_gpt_response: bool = True
    gpt_model: str = "gpt-6-luna"
    gpt_max_output_tokens: int = 80
    gpt_timeout_seconds: float = 5.0
    use_edge_tts: bool = True
    tts_voice: str = "ko-KR-SunHiNeural"
    call_device_token: str = ""
    # Separate credential for P4 video ingestion. Existing S3 POST remains unchanged.
    camera_ingest_token: str = ""
    camera_max_frame_bytes: int = 524288
    call_answer_timeout_seconds: float = 30.0
    # Initial administrator account: TUTUS / the password supplied during setup.
    # The password itself is never stored in source; this is a PBKDF2-SHA256 hash.
    admin_username: str = "TUTUS"
    admin_password_hash: str = "a3e14ee76395489cd948bcc5ca849cc0f87e08951c5dde7f042c326a3965462a"
    admin_password_salt: str = "hanmir-admin-v1"
    admin_session_hours: int = 8
    yolo_enabled: bool = True
    yolo_target_fps: float = Field(default=10.0, gt=0, le=30)
    yolo_trace_enabled: bool = True
    yolo_async_detail: bool = True
    yolo_head_detail_enabled: bool = True
    yolo_head_tight_probe: bool = False
    yolo_full_hand_evidence: bool = False
    yolo_gpu_voice_fps: float = Field(default=10.0, gt=0, le=10)
    camera_display_gamma: float = Field(default=1.0, ge=1.0, le=1.5)
    camera_preview_gamma: float | None = Field(default=None, ge=1.0, le=1.8)
    camera_preview_red_gain: float = Field(default=1.0, ge=0.8, le=1.2)
    camera_preview_blue_gain: float = Field(default=1.0, ge=0.8, le=1.2)
    camera_sharpen_amount: float = Field(default=0.0, ge=0.0, le=0.5)
    yolo_fast_openvino_gpu: bool = False
    yolo_detail_hybrid_gpu: bool = False
    yolo_detail_gpu960_model_path: str = ""
    yolo_vest_body_probe: bool = False
    yolo_detail_early_exit: bool = False
    yolo_detail_during_voice: bool = False
    yolo_openvino_model_path: str = str(BASE_DIR / 'best_openvino_model')
    yolo_detail_max_age_seconds: float = Field(default=1.5, gt=0, le=5)
    yolo_model_path: str = str(BASE_DIR / "best.pt")
    # Match backend/test_webcam.py: Ultralytics default confidence and 320px input.
    yolo_confidence: float = 0.25
    yolo_image_size: int = 320
    # Keep full-frame detection at 320 (empirically best for this model), then
    # inspect the tracked person ROI at the model's native 640 training size.
    yolo_ppe_detail_image_size: int = 640
    yolo_ppe_detail_960_enabled: bool = True
    yolo_ppe_detail_interval_seconds: float = 0.30
    yolo_person_track_seconds: float = 2.0
    yolo_person_confidence: float = 0.35
    # Camera upload and inference can skip frames.  Six seconds keeps the
    # three-frame PPE decision stable without treating an old sighting as live.
    yolo_ppe_window_seconds: float = 6.0
    yolo_ppe_worn_frames: int = 2
    yolo_ppe_person_frames: int = 3
    # Missing PPE is confirmed only after three consecutive person frames.
    yolo_ppe_missing_consecutive_frames: int = 3
    yolo_ppe_confidence: float = 0.45
    yolo_glove_confidence: float = 0.40
    yolo_vest_confidence: float = 0.40
    # Require a strong detection in three consecutive analyzed frames before
    # raising a fire incident. This favors avoiding false alarms.
    yolo_fire_confidence: float = 0.75
    yolo_fire_confirm_frames: int = 3
    yolo_smoke_confidence: float = 0.45
    yolo_smoke_confirm_frames: int = 2
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    @model_validator(mode="after")
    def ordered_uwb_quality_thresholds(self):
        if self.uwb_quality_gap_bad_db <= self.uwb_quality_gap_warn_db or self.uwb_quality_path_bad_samples <= self.uwb_quality_path_warn_samples:
            raise ValueError("bad signal thresholds must be greater than warning thresholds")
        return self

    @property
    def wake_word_alias_list(self) -> list[str]:
        return [item.strip() for item in self.wake_word_aliases.split(",") if item.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
