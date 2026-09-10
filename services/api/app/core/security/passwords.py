from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a staff password with pwdlib's recommended Argon2 parameters."""

    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a staff password, treating unrecognized hashes as invalid."""

    try:
        return _password_hash.verify(password, password_hash)
    except UnknownHashError:
        return False
