import base64

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.core.config import AppEnvironment, Settings


def test_settings_load_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://db/otklik")
    monkeypatch.setenv("VALKEY_URL", "redis://cache:6379/0")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-value")
    monkeypatch.setenv("TRACK_HMAC_SECRET", "test-track-value")
    monkeypatch.setenv("RATE_LIMIT_HMAC_SECRET", "test-rate-value")
    monkeypatch.setenv("REFRESH_TOKEN_HMAC_SECRET", "test-refresh-value")
    monkeypatch.setenv("APPLICANT_ACCESS_JWT_SECRET", "test-applicant-access-value")
    monkeypatch.setenv("CONTENT_ENCRYPTION_KEY", "test-encryption-value")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")

    settings = Settings(_env_file=None)

    assert settings.app_env is AppEnvironment.TESTING
    assert settings.database_url == "postgresql+asyncpg://db/otklik"
    assert settings.valkey_url == "redis://cache:6379/0"
    assert settings.jwt_secret is not None
    assert settings.jwt_secret.get_secret_value() == "test-jwt-value"
    assert settings.applicant_access_jwt_secret is not None
    assert settings.applicant_access_jwt_secret.get_secret_value() == "test-applicant-access-value"
    assert settings.cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]


def test_production_rejects_missing_secrets() -> None:
    with pytest.raises(PydanticValidationError, match="Production requires environment variables"):
        Settings(_env_file=None, app_env="production")


def test_production_rejects_wildcard_cors() -> None:
    encryption_key = base64.urlsafe_b64encode(b"k" * 32).decode("ascii")
    with pytest.raises(PydanticValidationError, match="Wildcard CORS origins"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="j" * 32,
            track_hmac_secret="t" * 32,
            rate_limit_hmac_secret="r" * 32,
            refresh_token_hmac_secret="f" * 32,
            applicant_access_jwt_secret="a" * 32,
            content_encryption_key=encryption_key,
            cors_origins=["*"],
        )


def test_production_rejects_compose_demo_secrets() -> None:
    with pytest.raises(ValueError, match="forbids built-in demo secrets"):
        Settings(
            _env_file=None,
            app_env=AppEnvironment.PRODUCTION,
            jwt_secret="demo-only-jwt-secret-change-before-prod-2026",
            track_hmac_secret="demo-only-track-hmac-change-before-prod-2026",
            rate_limit_hmac_secret="demo-only-rate-hmac-change-before-prod-2026",
            refresh_token_hmac_secret="demo-only-refresh-hmac-change-before-prod-2026",
            applicant_access_jwt_secret="demo-only-applicant-jwt-change-before-prod-2026",
            content_encryption_key="b3RrbGlrLWRlbW8tY29udGVudC1rZXktMzItYnl0ZSE=",
        )


def test_production_rejects_invalid_encryption_key() -> None:
    with pytest.raises(PydanticValidationError, match="exactly 32 bytes"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="j" * 32,
            track_hmac_secret="t" * 32,
            rate_limit_hmac_secret="r" * 32,
            refresh_token_hmac_secret="f" * 32,
            applicant_access_jwt_secret="a" * 32,
            content_encryption_key=base64.urlsafe_b64encode(b"too-short").decode("ascii"),
        )


def test_production_rejects_short_authentication_secrets() -> None:
    encryption_key = base64.urlsafe_b64encode(b"k" * 32).decode("ascii")

    with pytest.raises(PydanticValidationError, match="at least 32 bytes"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="short",
            track_hmac_secret="t" * 32,
            rate_limit_hmac_secret="r" * 32,
            refresh_token_hmac_secret="f" * 32,
            applicant_access_jwt_secret="a" * 32,
            content_encryption_key=encryption_key,
        )


def test_applicant_access_secret_must_be_separate() -> None:
    shared_secret = "s" * 32
    with pytest.raises(PydanticValidationError, match="must not reuse"):
        Settings(
            _env_file=None,
            jwt_secret=shared_secret,
            applicant_access_jwt_secret=shared_secret,
        )
