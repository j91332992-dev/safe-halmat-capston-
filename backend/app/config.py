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
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    openai_api_key: str | None = None
    use_whisper_stt: bool = True
    stt_model: str = "gpt-4o-mini-transcribe"
    stt_language: str = "ko"
    wake_word_aliases: str = "세이피,세이 피,세이프티"
    wake_followup_seconds: float = 8.0
    use_gpt_response: bool = True
    gpt_model: str = "gpt-5.6-sol"
    gpt_max_output_tokens: int = 160
    use_edge_tts: bool = True
    tts_voice: str = "ko-KR-SunHiNeural"
    yolo_enabled: bool = True
    yolo_model_path: str = str(BASE_DIR / "best.pt")
    yolo_confidence: float = 0.15
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    @property
    def wake_word_alias_list(self) -> list[str]:
        return [item.strip() for item in self.wake_word_aliases.split(",") if item.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()


