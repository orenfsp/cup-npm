import json
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def _default_env_files() -> tuple[Path, ...]:
    working_directory = Path.cwd().resolve()
    if working_directory.name == "api" and working_directory.parent.name == "services":
        repository_env = working_directory.parent.parent / ".env"
        return (repository_env, working_directory / ".env")
    return (working_directory / ".env",)


class Settings(BaseSettings):
    """Environment-backed application settings.

    Secrets are optional while unused in development and testing. Production
    validation requires every declared secret to be supplied by the environment.
    """

    model_config = SettingsConfigDict(
        env_file=_default_env_files(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Otklik API"
    api_version: str = "v1"
    app_env: AppEnvironment = AppEnvironment.DEVELOPMENT
    log_level: LogLevel = "INFO"

    database_url: str = "postgresql+asyncpg://otklik@localhost:5432/otklik"
    valkey_url: str = "redis://localhost:6379/0"

    jwt_secret: SecretStr | None = None
    track_hmac_secret: SecretStr | None = None
    rate_limit_hmac_secret: SecretStr | None = None
    refresh_token_hmac_secret: SecretStr | None = None
    applicant_access_jwt_secret: SecretStr | None = None
    content_encryption_key: SecretStr | None = None

    jwt_issuer: str = Field(default="otklik-api", min_length=1, max_length=200)
    jwt_audience: str = Field(default="otklik-staff", min_length=1, max_length=200)
    access_token_ttl_minutes: int = Field(default=15, ge=1, le=60)
    refresh_session_ttl_days: int = Field(default=7, ge=1, le=30)
    refresh_cookie_name: str = Field(default="otklik_staff_refresh", pattern=r"^[A-Za-z0-9_-]+$")
    login_rate_limit_attempts: int = Field(default=5, ge=1, le=100)
    login_rate_limit_window_seconds: int = Field(default=300, ge=1, le=3600)

    applicant_access_jwt_issuer: str = Field(default="otklik-api", min_length=1, max_length=200)
    applicant_access_jwt_audience: str = Field(
        default="otklik-appeal-access", min_length=1, max_length=200
    )
    applicant_access_ttl_minutes: int = Field(default=30, ge=5, le=120)
    applicant_access_cookie_name: str = Field(
        default="otklik_appeal_access", pattern=r"^[A-Za-z0-9_-]+$"
    )
    track_access_rate_limit_attempts: int = Field(default=5, ge=1, le=100)
    track_access_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    appeal_submission_rate_limit_attempts: int = Field(default=10, ge=1, le=100)
    appeal_submission_rate_limit_window_seconds: int = Field(default=3600, ge=60, le=86400)
    operator_overdue_hours: int = Field(default=24, ge=1, le=720)
    applicant_max_returns: int = Field(default=2, ge=1, le=5)
    expert_composer_lock_ttl_seconds: int = Field(default=30, ge=10, le=120)

    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: str | None = None
    smtp_from_name: str = Field(default="Отклик", min_length=1, max_length=120)
    smtp_use_tls: bool = True
    staff_invite_ttl_hours: int = Field(default=24, ge=1, le=168)
    staff_frontend_base_url: str = Field(
        default="http://localhost:3000", min_length=1, max_length=500
    )

    attachment_storage_path: Path = Path("var/private/attachments")
    attachment_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=25 * 1024 * 1024)
    attachment_max_count: int = Field(default=5, ge=1, le=10)
    attachment_max_pixels: int = Field(default=40_000_000, ge=1_000_000, le=100_000_000)
    crisis_support_title: str = Field(
        default="Помощь в экстренной ситуации", min_length=1, max_length=120
    )
    crisis_support_message: str = Field(
        default=(
            "Если прямо сейчас есть угроза жизни или безопасности, обратитесь в местную "
            "экстренную службу или к взрослому, которому доверяете."
        ),
        min_length=1,
        max_length=500,
    )
    crisis_support_phone: str | None = Field(default=None, max_length=60)
    crisis_support_url: str | None = Field(default=None, max_length=500)
    crisis_support_requires_organizer_verification: bool = True

    demo_operator_login: str = "demo_operator"
    demo_operator_password: SecretStr | None = None
    demo_expert_login: str = "demo_expert"
    demo_expert_password: SecretStr | None = None
    demo_psychologist_login: str = "demo_psychologist"
    demo_psychologist_password: SecretStr | None = None
    demo_lawyer_login: str = "demo_lawyer"
    demo_lawyer_password: SecretStr | None = None
    demo_social_login: str = "demo_social"
    demo_social_password: SecretStr | None = None
    demo_conflict_login: str = "demo_conflict"
    demo_conflict_password: SecretStr | None = None
    demo_admin_login: str = "demo_admin"
    demo_admin_password: SecretStr | None = None

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    healthcheck_timeout_seconds: float = Field(default=3.0, gt=0, le=30)

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if not isinstance(value, str):
            return value

        raw_value = value.strip()
        if not raw_value:
            return []
        if raw_value.startswith("["):
            parsed = json.loads(raw_value)
            if not isinstance(parsed, list):
                raise ValueError("CORS_ORIGINS JSON must be an array")
            return parsed
        return [origin.strip() for origin in raw_value.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if "*" in self.cors_origins:
            raise ValueError("Wildcard CORS origins are forbidden when credentials are enabled")
        applicant_secret = self.applicant_access_jwt_secret
        if applicant_secret is not None:
            applicant_secret_value = applicant_secret.get_secret_value()
            forbidden_reuse = {
                secret.get_secret_value()
                for secret in (
                    self.jwt_secret,
                    self.track_hmac_secret,
                    self.rate_limit_hmac_secret,
                    self.refresh_token_hmac_secret,
                    self.content_encryption_key,
                )
                if secret is not None
            }
            if applicant_secret_value in forbidden_reuse:
                raise ValueError(
                    "Applicant access JWT secret must not reuse any other application secret"
                )
        if self.app_env is not AppEnvironment.PRODUCTION:
            return self

        secrets = {
            "JWT_SECRET": self.jwt_secret,
            "TRACK_HMAC_SECRET": self.track_hmac_secret,
            "RATE_LIMIT_HMAC_SECRET": self.rate_limit_hmac_secret,
            "REFRESH_TOKEN_HMAC_SECRET": self.refresh_token_hmac_secret,
            "APPLICANT_ACCESS_JWT_SECRET": self.applicant_access_jwt_secret,
            "CONTENT_ENCRYPTION_KEY": self.content_encryption_key,
        }
        missing = [
            name
            for name, value in secrets.items()
            if value is None or not value.get_secret_value().strip()
        ]
        if missing:
            raise ValueError(f"Production requires environment variables: {', '.join(missing)}")
        insecure_demo_values = {
            "demo-only-jwt-secret-change-before-prod-2026",
            "demo-only-track-hmac-change-before-prod-2026",
            "demo-only-rate-hmac-change-before-prod-2026",
            "demo-only-refresh-hmac-change-before-prod-2026",
            "demo-only-applicant-jwt-change-before-prod-2026",
            "b3RrbGlrLWRlbW8tY29udGVudC1rZXktMzItYnl0ZSE=",
        }
        demo_secrets = [
            name
            for name, value in secrets.items()
            if value is not None and value.get_secret_value() in insecure_demo_values
        ]
        if demo_secrets:
            raise ValueError(
                "Production forbids built-in demo secrets: " + ", ".join(demo_secrets)
            )
        short_secrets = [
            name
            for name, value in secrets.items()
            if name != "CONTENT_ENCRYPTION_KEY"
            and value is not None
            and len(value.get_secret_value().encode("utf-8")) < 32
        ]
        if short_secrets:
            raise ValueError(
                "Production secrets must be at least 32 bytes: " + ", ".join(short_secrets)
            )
        from app.core.crypto.encryption import decode_content_encryption_key

        encryption_key = self.content_encryption_key
        if encryption_key is not None:
            decode_content_encryption_key(encryption_key.get_secret_value())
        return self

    @property
    def api_prefix(self) -> str:
        return f"/api/{self.api_version}"

    @property
    def refresh_cookie_secure(self) -> bool:
        return self.app_env is AppEnvironment.PRODUCTION

    @property
    def applicant_access_cookie_secure(self) -> bool:
        return self.app_env is AppEnvironment.PRODUCTION

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from_email)


@lru_cache
def get_settings() -> Settings:
    return Settings()
