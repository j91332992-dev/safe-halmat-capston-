from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
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
    location_stationary_radius_m: float = 0.15
    # Keep receiving positions continuously, but leave a stationary marker fixed
    # until movement from the last accepted position reaches 30 cm twice.
    location_move_start_m: float = 0.30
    location_move_confirm_samples: int = 2
    location_stop_step_m: float = 0.08
    location_stop_confirm_samples: int = 5
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    openai_api_key: str | None = None
    use_whisper_stt: bool = True
    stt_model: str = "gpt-4o-mini-transcribe"
    stt_language: str = "ko"
    stt_prompt: str = "한국어 산업 안전 현장 대화입니다. 호출어 투투스와 작업자의 짧은 명령을 정확히 받아쓰고, 들리지 않는 내용은 추측하지 마세요."
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
    gpt_model: str = "gpt-5.6-sol"
    gpt_max_output_tokens: int = 80
    use_edge_tts: bool = True
    tts_voice: str = "ko-KR-SunHiNeural"
    call_device_token: str = ""
    call_answer_timeout_seconds: float = 30.0
    yolo_enabled: bool = True
    yolo_model_path: str = str(BASE_DIR / "best.pt")
    # Match backend/test_webcam.py: Ultralytics default confidence and 320px input.
    yolo_confidence: float = 0.25
    yolo_image_size: int = 320
    # Keep full-frame detection at 320 (empirically best for this model), then
    # inspect the tracked person ROI at the model's native 640 training size.
    yolo_ppe_detail_image_size: int = 640
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
    yolo_fire_confidence: float = 0.50
    yolo_fire_confirm_frames: int = 3
    yolo_smoke_confidence: float = 0.45
    yolo_smoke_confirm_frames: int = 2
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    @property
    def wake_word_alias_list(self) -> list[str]:
        return [item.strip() for item in self.wake_word_aliases.split(",") if item.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()


