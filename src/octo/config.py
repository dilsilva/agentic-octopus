"""12-factor configuration — everything comes from the environment (or .env locally)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://octo:octo@localhost:5432/octo"
    anthropic_api_key: str = ""
    # Model behind the 'octo/claude' virtual model (chat). Billable — only routes
    # when anthropic_api_key is set. claude-haiku-4-5 is the budget alternative.
    anthropic_default_model: str = "claude-opus-4-8"

    @property
    def anthropic_key_set(self) -> bool:
        """True only for a real key — the .env.example placeholder doesn't count."""
        return bool(self.anthropic_api_key) and "REPLACE" not in self.anthropic_api_key

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # 'octo/auto' = the smart router: tries preferred :free models in order,
    # cooling down congested/dead ones. Pin a single model id here to bypass it.
    openrouter_default_model: str = "octo/auto"
    # Router candidates, best-first (probed 2026-07-18). Only the first 3 are sent
    # (OpenRouter caps the fallback array at 3); the rest are warm spares to promote.
    openrouter_preferred_models: str = (
        "nvidia/nemotron-3-super-120b-a12b:free,"
        "google/gemma-4-26b-a4b-it:free,"
        "tencent/hy3:free,"
        "qwen/qwen3-next-80b-a3b-instruct:free,"
        "google/gemma-4-31b-it:free"
    )
    # Hard cost guard: only :free models are allowed until explicitly flipped.
    openrouter_allow_paid: bool = False
    octo_api_token: str = "change-me"
    # Optional client-scoped token: valid ONLY on /chat/* and /v1/* (given to chat UIs).
    octo_chat_token: str = ""
    chat_provider: str = "openrouter"
    chat_context_budget: int = 8000  # est. tokens for the sliding context window
    octo_api_url: str = "http://localhost:8000"
    octo_env: str = "local"
    log_level: str = "info"
    worker_concurrency: int = 1
    scheduler_enabled: bool = True
    agents_dir: str = "agents"
    data_dir: str = "data"


settings = Settings()
