import hashlib
import hmac


def hmac_sha256(secret: str | bytes, value: str | bytes) -> bytes:
    """Return a binary HMAC-SHA256 digest without logging either input."""

    secret_bytes = secret.encode("utf-8") if isinstance(secret, str) else secret
    value_bytes = value.encode("utf-8") if isinstance(value, str) else value
    if not secret_bytes:
        raise ValueError("HMAC secret must not be empty")
    return hmac.new(secret_bytes, value_bytes, hashlib.sha256).digest()


def track_lookup_digest(secret: str | bytes, normalized_track_code: str) -> bytes:
    """Digest an already-normalized track code for future indexed lookup."""

    return hmac_sha256(secret, normalized_track_code)


def rate_limit_digest(secret: str | bytes, transient_value: str | bytes) -> bytes:
    """Pseudonymize a transient rate-limit value without persisting the raw value."""

    return hmac_sha256(secret, transient_value)


def refresh_token_digest(secret: str | bytes, refresh_token: str) -> bytes:
    """Digest a high-entropy refresh token for server-side session lookup."""

    return hmac_sha256(secret, refresh_token)
