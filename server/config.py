"""Server-layer configuration (DB path, etc.)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_path: str = "omnispy.db"
    http_host: str = "127.0.0.1"
    http_port: int = 8000


server_settings = ServerSettings()
