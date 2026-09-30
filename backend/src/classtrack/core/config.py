"""Application settings, loaded from the environment (prefix ``CLASSTRACK_``)."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CLASSTRACK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_name: str = "ClassTrack"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    database_url: str = "sqlite+aiosqlite:///./classtrack.db"
    db_echo: bool = False

    #: NoDecode keeps pydantic-settings from JSON-parsing this before the
    #: validator below runs, so a plain "a,b" or "*" works from the environment.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["*"])

    api_v1_prefix: str = "/api/v1"

    # --- auth ---------------------------------------------------------------
    #: Signing key for session JWTs. Must be set in production.
    jwt_secret: str = "dev-only-insecure-secret-please-change-me-32b"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 12
    session_cookie: str = "classtrack_session"
    #: False in development so the cookie works over plain HTTP on localhost.
    cookie_secure: bool = False

    # --- monitoring rules (BR-05, BR-06) ------------------------------------
    #: Minutes after scheduled start before a confirmed absence becomes MISSED.
    missed_threshold_minutes: int = 30
    #: Minutes staff have to submit any input before the class is NOT_CHECKED.

    #: Every clock comparison happens in this zone. Stored timestamps are UTC.
    timezone: str = "Asia/Dhaka"
    department: str = "cse"

    #: Seconds between sweep passes. 0 disables the loop (used by tests).
    sweep_interval_seconds: int = 60

    # --- email ----------------------------------------------------------------
    #: Resend API key. Unset disables email; in-app notifications are unaffected.
    #: Leave it unset in development: the faculty directory holds real addresses.
    resend_api_key: str | None = None
    #: Must be on a domain verified in Resend.
    email_from: str = "ClassTrack <noreply@bitstreamhq.com>"
    #: Public origin for links in emails, e.g. "https://class.bitstreamhq.com".
    public_url: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()
