import base64

import pytest

from app.core.config import AppEnvironment, Settings


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TESTING,
        database_url="postgresql+asyncpg://otklik@localhost:5432/otklik_test",
        valkey_url="redis://localhost:6379/15",
        jwt_secret="j" * 64,
        track_hmac_secret="t" * 64,
        rate_limit_hmac_secret="r" * 64,
        refresh_token_hmac_secret="f" * 64,
        applicant_access_jwt_secret="a" * 64,
        content_encryption_key=base64.urlsafe_b64encode(b"k" * 32).decode("ascii"),
        cors_origins=["http://localhost:3000"],
    )
