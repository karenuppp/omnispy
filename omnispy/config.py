"""Application settings loaded from environment + .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # X (Twitter)
    x_cookie: str = ""

    # LLM (Ollama, OpenAI-compatible)
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen2.5:7b"
    ollama_api_key: str = "ollama"

    # HTTP server
    http_host: str = "127.0.0.1"
    http_port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()