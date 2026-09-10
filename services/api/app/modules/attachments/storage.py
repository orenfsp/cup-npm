import re
import secrets
from pathlib import Path

from app.core.errors import InfrastructureError

_STORAGE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{40,80}$")


class PrivateAttachmentStorage:
    """Filesystem-backed private blob storage with opaque, extensionless keys."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def write(self, encrypted_blob: bytes) -> str:
        self._root.mkdir(parents=True, exist_ok=True)
        for _attempt in range(5):
            key = secrets.token_urlsafe(32)
            target = self._target(key)
            try:
                with target.open("xb") as output:
                    output.write(encrypted_blob)
                return key
            except FileExistsError:
                continue
            except OSError as exc:
                raise InfrastructureError("Private attachment storage is unavailable.") from exc
        raise InfrastructureError("A unique attachment storage key could not be allocated.")

    def delete(self, key: str) -> None:
        try:
            self._target(key).unlink(missing_ok=True)
        except OSError as exc:
            raise InfrastructureError("Private attachment cleanup failed.") from exc

    def read(self, key: str) -> bytes:
        try:
            return self._target(key).read_bytes()
        except OSError as exc:
            raise InfrastructureError("Private attachment storage is unavailable.") from exc

    def _target(self, key: str) -> Path:
        if _STORAGE_KEY_PATTERN.fullmatch(key) is None:
            raise ValueError("Invalid attachment storage key")
        target = (self._root / key).resolve()
        if target.parent != self._root:
            raise ValueError("Invalid attachment storage key")
        return target
