"""Application settings loaded from .env file with pydantic-settings."""

from typing import List

from pydantic import field_validator
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
    # How many trailing IPv4 octets to mask in logs (e.g. rate-limit warnings).
    # 1 keeps "192.168.1.x", 2 keeps "192.168.x.x". Keeps the prefix visible so
    # repeat offenders can still be spotted while the host part stays anonymous.
    log_ip_mask_octets: int = 1
    forwarded_allow_ips: str = "*"
    # Whether to expose the interactive API docs (/api/docs) and the OpenAPI
    # schema (/api/openapi.json). Disable in production to reduce the public
    # attack surface — the endpoints then return 404.
    enable_docs: bool = True

    @field_validator("log_ip_mask_octets")
    @classmethod
    def validate_mask_octets(cls, value: int) -> int:
        """Clamp the mask depth to the valid 1..4 range."""
        return max(1, min(value, 4))


settings: Settings = Settings()
