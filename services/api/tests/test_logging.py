import logging

import pytest

from app.core.logging.config import SensitiveDataFilter


@pytest.mark.parametrize(
    "field_name",
    [
        "password",
        "password_hash",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
        "set-cookie",
    ],
)
def test_sensitive_auth_log_assignments_are_redacted(field_name: str) -> None:
    record = logging.LogRecord(
        "test",
        logging.INFO,
        __file__,
        1,
        f"{field_name}=must-not-appear",
        (),
        None,
    )

    SensitiveDataFilter(()).filter(record)

    assert "must-not-appear" not in record.getMessage()
    assert "<redacted>" in record.getMessage()
