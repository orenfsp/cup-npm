import base64
import binascii
import json
import os
import re

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

CURRENT_KEY_VERSION = 1
NONCE_SIZE = 12
TAG_SIZE = 16

type JSONValue = None | bool | int | float | str | list[JSONValue] | dict[str, JSONValue]


class InvalidEncryptionKeyError(ValueError):
    """Raised when configured AES key material is not a URL-safe base64 256-bit key."""


class DecryptionError(ValueError):
    """Raised when an encrypted envelope is malformed or cannot be authenticated."""


def decode_content_encryption_key(encoded_key: str) -> bytes:
    """Decode and validate a URL-safe base64 encoded 32-byte AES key."""

    candidate = encoded_key.strip()
    if not candidate:
        raise InvalidEncryptionKeyError("Content encryption key must not be empty")
    if re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", candidate) is None:
        raise InvalidEncryptionKeyError("Content encryption key must be valid URL-safe base64")

    padding = "=" * (-len(candidate) % 4)
    try:
        key = base64.b64decode((candidate + padding).encode("ascii"), altchars=b"-_", validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError) as error:
        raise InvalidEncryptionKeyError(
            "Content encryption key must be valid URL-safe base64"
        ) from error

    if len(key) != 32:
        raise InvalidEncryptionKeyError("Content encryption key must decode to exactly 32 bytes")
    return key


class ContentCrypto:
    """AES-256-GCM encryption for content fields.

    The binary envelope is ``version (1 byte) || nonce (12 bytes) ||
    ciphertext_and_tag``. AES-GCM appends a 16-byte authentication tag. A new
    cryptographically random nonce is generated for every encryption operation.
    Version 1 is the only supported key version in this phase.
    """

    def __init__(self, encoded_key: str, *, key_version: int = CURRENT_KEY_VERSION) -> None:
        if key_version != CURRENT_KEY_VERSION:
            raise ValueError(f"Unsupported content key version: {key_version}")
        self._cipher = AESGCM(decode_content_encryption_key(encoded_key))
        self.key_version = key_version

    def encrypt_bytes(self, plaintext: bytes, *, aad: bytes | None = None) -> bytes:
        nonce = os.urandom(NONCE_SIZE)
        ciphertext_and_tag = self._cipher.encrypt(nonce, plaintext, aad)
        return bytes((self.key_version,)) + nonce + ciphertext_and_tag

    def decrypt_bytes(self, envelope: bytes, *, aad: bytes | None = None) -> bytes:
        minimum_size = 1 + NONCE_SIZE + TAG_SIZE
        if len(envelope) < minimum_size:
            raise DecryptionError("Encrypted payload is malformed")

        version = envelope[0]
        if version != self.key_version:
            raise DecryptionError(f"Unsupported encrypted payload version: {version}")

        nonce = envelope[1 : 1 + NONCE_SIZE]
        ciphertext_and_tag = envelope[1 + NONCE_SIZE :]
        try:
            return self._cipher.decrypt(nonce, ciphertext_and_tag, aad)
        except InvalidTag as error:
            raise DecryptionError("Encrypted payload authentication failed") from error

    def encrypt_text(self, plaintext: str, *, aad: bytes | None = None) -> bytes:
        return self.encrypt_bytes(plaintext.encode("utf-8"), aad=aad)

    def decrypt_text(self, envelope: bytes, *, aad: bytes | None = None) -> str:
        plaintext = self.decrypt_bytes(envelope, aad=aad)
        try:
            return plaintext.decode("utf-8")
        except UnicodeDecodeError as error:
            raise DecryptionError("Decrypted payload is not valid UTF-8 text") from error

    def encrypt_json(self, value: JSONValue, *, aad: bytes | None = None) -> bytes:
        plaintext = json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        return self.encrypt_bytes(plaintext, aad=aad)

    def decrypt_json(self, envelope: bytes, *, aad: bytes | None = None) -> JSONValue:
        plaintext = self.decrypt_bytes(envelope, aad=aad)
        try:
            return json.loads(plaintext)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DecryptionError("Decrypted payload is not valid JSON") from error
