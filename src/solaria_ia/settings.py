from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SOLARIA_", env_file=".env", extra="ignore")

    provider_mode: Literal["mock", "ollama"] = "mock"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:1.7b"
    ollama_review_model: str = "gemma3:1b"
    ollama_keep_alive: str = "0"
    request_timeout_seconds: float = Field(default=120, ge=1, le=600)
    max_input_chars: int = Field(default=12_000, ge=500, le=100_000)
    max_output_tokens: int = Field(default=900, ge=32, le=8_192)
    review_max_output_tokens: int = Field(default=160, ge=32, le=512)
    review_provider: Literal["ollama", "gemini", "copilot"] = "ollama"
    gemini_enabled: bool = False
    gemini_free_tier_confirmed: bool = False
    copilot_enabled: bool = False
    copilot_free_tier_confirmed: bool = False
    copilot_model: str = "auto"
    copilot_daily_call_limit: int = Field(default=1, ge=0, le=10)
    copilot_daily_token_limit: int = Field(default=4000, ge=256, le=20000)
    copilot_max_ai_credits_per_run: float = Field(default=1.0, gt=0, le=100)
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_daily_call_limit: int = Field(default=10, ge=0, le=100)
    gemini_daily_token_limit: int = Field(default=10000, ge=1000, le=100000)
    max_total_tokens_per_run: int = Field(default=6000, ge=256, le=100000)
    daily_usage_db_path: str = "artifacts/usage.sqlite3"
    max_calls_per_run: int = Field(default=3, ge=1, le=10)
    local_parallelism: int = Field(default=1, ge=1, le=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
