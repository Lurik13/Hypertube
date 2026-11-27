"""Runtime configuration, read once from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    # Signs the short-lived cookie that carries the OAuth state.
    secret_key: SecretStr = Field(min_length=32)

    frontend_url: str = "http://localhost:5173"
    public_api_url: str = "http://localhost:8000"

    session_cookie_name: str = "hypertube_session"
    session_ttl_hours: int = Field(default=168, gt=0)
    cookie_secure: bool = True
    password_reset_ttl_minutes: int = Field(default=30, gt=0)

    mail_from: str = "Hypertube <no-reply@hypertube.local>"
    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_starttls: bool = False

    fortytwo_client_id: str = ""
    fortytwo_client_secret: SecretStr = SecretStr("")
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")

    broker_url: str = "redis://valkey:6379/0"
    media_root: Path = Path("/data/media")
    movie_retention_days: int = Field(default=30, gt=0)
    cleanup_interval_minutes: int = Field(default=60, gt=0)

    @field_validator("frontend_url", "public_api_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
