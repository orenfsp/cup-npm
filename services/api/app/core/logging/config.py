import logging
import re
from collections.abc import Iterable

_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(password(?:_hash)?|(?:access_|refresh_)?token|jwt|authorization|cookie|"
    r"set-cookie|secret|encryption_key|contact_data|appeal_content)"
    r"\b(\s*[:=]\s*)([^\r\n,;]+)"
)


class SensitiveDataFilter(logging.Filter):
    """Last-resort redaction for values that must never reach application logs."""

    def __init__(self, sensitive_values: Iterable[str]) -> None:
        super().__init__()
        self.sensitive_values = tuple(value for value in sensitive_values if len(value) >= 4)

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for value in self.sensitive_values:
            message = message.replace(value, "<redacted>")
        record.msg = _SENSITIVE_ASSIGNMENT.sub(r"\1\2<redacted>", message)
        record.args = ()
        return True


def configure_logging(log_level: str, *, sensitive_values: Iterable[str] = ()) -> None:
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        force=True,
    )
    redaction_filter = SensitiveDataFilter(sensitive_values)
    for handler in logging.getLogger().handlers:
        handler.addFilter(redaction_filter)

    # The default Uvicorn access log contains client IP addresses. Otklik does not log them.
    logging.getLogger("uvicorn.access").disabled = True
