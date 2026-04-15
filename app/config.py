from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str
    claude_model: str = "claude-sonnet-4-5"

    # FortiDLP event stream
    fortidlp_base_url: str
    fortidlp_stream_id: str
    fortidlp_stream_token: str

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"


def get_settings() -> Settings:
    return Settings()
