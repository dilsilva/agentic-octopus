"""12-factor configuration — everything comes from the environment (or .env locally)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://octo:octo@localhost:5432/octo"
    anthropic_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_default_model: str = "nvidia/nemotron-3-super-120b-a12b:free"
    # Hard cost guard: only :free models are allowed until explicitly flipped.
    openrouter_allow_paid: bool = False
    octo_api_token: str = "change-me"
    octo_api_url: str = "http://localhost:8000"
    octo_env: str = "local"
    log_level: str = "info"
    worker_concurrency: int = 1
    scheduler_enabled: bool = True
    agents_dir: str = "agents"
    data_dir: str = "data"


settings = Settings()
