"""Application settings loaded from .env file with pydantic-settings."""

from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env file with pydantic-settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:///./data/telemetry.db"
    log_level: str = "INFO"
    data_dir: str = "./data"
    cors_origins: List[str] = ["http://localhost:8001"]
    # Maximum number of telemetry requests per IP per minute. The dashboard is
    # public and ingestion is intentionally unauthenticated (the client is
    # open source), so rate limiting is the primary spam defence.
    rate_limit_per_minute: int = 4
    public_app_url: str = "http://localhost:8001"
    forwarded_allow_ips: str = "*"


settings: Settings = Settings()
