from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SOLARIA_", env_file=".env", extra="ignore")

    provider_mode: Literal["mock", "ollama"] = "mock"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"
    ollama_review_model: str = "gemma3:1b"
    ollama_keep_alive: str = "0"
    request_timeout_seconds: float = Field(default=120, ge=1, le=600)
    max_input_chars: int = Field(default=12_000, ge=500, le=100_000)
    max_output_tokens: int = Field(default=900, ge=32, le=8_192)
    review_max_output_tokens: int = Field(default=160, ge=32, le=512)
    max_calls_per_run: int = Field(default=3, ge=1, le=10)
    local_parallelism: int = Field(default=1, ge=1, le=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
