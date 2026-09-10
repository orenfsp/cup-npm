import re
import secrets

TRACK_PREFIX = "ОТК"
TRACK_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_TRACK_PATTERN = re.compile(
    rf"^{TRACK_PREFIX}-([{TRACK_ALPHABET}]{{4}})-([{TRACK_ALPHABET}]{{4}})$"
)


def generate_track_number() -> str:
    """Generate a copy-friendly track capability with 40+ bits of entropy."""

    significant = "".join(secrets.choice(TRACK_ALPHABET) for _ in range(8))
    return f"{TRACK_PREFIX}-{significant[:4]}-{significant[4:]}"


def normalize_track_number(value: str) -> str:
    """Normalize benign formatting without accepting ambiguous characters."""

    compact = re.sub(r"[\s\-‐‑‒–—]+", "", value.strip().upper())
    if compact.startswith("OTK"):
        compact = TRACK_PREFIX + compact[3:]
    if not compact.startswith(TRACK_PREFIX) or len(compact) != 11:
        raise ValueError("Invalid track number")
    formatted = f"{TRACK_PREFIX}-{compact[3:7]}-{compact[7:11]}"
    if _TRACK_PATTERN.fullmatch(formatted) is None:
        raise ValueError("Invalid track number")
    return formatted
