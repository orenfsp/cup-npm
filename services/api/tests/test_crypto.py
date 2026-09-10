import base64

import pytest

from app.core.crypto import (
    ContentCrypto,
    DecryptionError,
    InvalidEncryptionKeyError,
    hmac_sha256,
    rate_limit_digest,
    track_lookup_digest,
)


@pytest.fixture
def encoded_key() -> str:
    return base64.urlsafe_b64encode(b"a" * 32).decode("ascii")


@pytest.fixture
def crypto(encoded_key: str) -> ContentCrypto:
    return ContentCrypto(encoded_key)


def test_crypto_text_round_trip(crypto: ContentCrypto) -> None:
    plaintext = "Мне нужна помощь"

    assert crypto.decrypt_text(crypto.encrypt_text(plaintext)) == plaintext


def test_crypto_bytes_round_trip(crypto: ContentCrypto) -> None:
    plaintext = b"\x00private binary content\xff"

    assert crypto.decrypt_bytes(crypto.encrypt_bytes(plaintext)) == plaintext


def test_crypto_json_round_trip(crypto: ContentCrypto) -> None:
    payload = {"answers": [True, None, 3], "context": "sensitive"}

    assert crypto.decrypt_json(crypto.encrypt_json(payload)) == payload


def test_crypto_uses_a_fresh_nonce(crypto: ContentCrypto) -> None:
    first = crypto.encrypt_text("same plaintext")
    second = crypto.encrypt_text("same plaintext")

    assert first != second
    assert first[0] == crypto.key_version == 1


def test_crypto_rejects_tampered_ciphertext(crypto: ContentCrypto) -> None:
    envelope = bytearray(crypto.encrypt_text("private"))
    envelope[-1] ^= 1

    with pytest.raises(DecryptionError, match="authentication failed"):
        crypto.decrypt_text(bytes(envelope))


def test_crypto_rejects_wrong_aad(crypto: ContentCrypto) -> None:
    envelope = crypto.encrypt_text("private", aad=b"appeal:one")

    with pytest.raises(DecryptionError, match="authentication failed"):
        crypto.decrypt_text(envelope, aad=b"appeal:two")


@pytest.mark.parametrize("invalid_key", ["", "not-base64!", "c2hvcnQ="])
def test_crypto_rejects_invalid_key(invalid_key: str) -> None:
    with pytest.raises(InvalidEncryptionKeyError):
        ContentCrypto(invalid_key)


def test_hmac_is_deterministic() -> None:
    assert track_lookup_digest("track-secret", "OTK-ABC") == track_lookup_digest(
        "track-secret", "OTK-ABC"
    )
    assert len(track_lookup_digest("track-secret", "OTK-ABC")) == 32


def test_different_hmac_secrets_produce_different_digests() -> None:
    assert hmac_sha256("secret-one", "transient") != hmac_sha256("secret-two", "transient")


def test_rate_limit_digest_is_deterministic() -> None:
    assert rate_limit_digest("rate-secret", b"transient-value") == rate_limit_digest(
        "rate-secret", b"transient-value"
    )
