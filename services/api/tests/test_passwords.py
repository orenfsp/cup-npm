from app.core.security.passwords import hash_password, verify_password


def test_password_hash_and_verify() -> None:
    password = "correct horse battery staple"
    password_hash = hash_password(password)

    assert verify_password(password, password_hash)
    assert not verify_password("wrong password", password_hash)


def test_password_hash_is_not_plaintext() -> None:
    password = "staff password"

    assert hash_password(password) != password


def test_unrecognized_password_hash_is_rejected() -> None:
    assert not verify_password("password", "not-a-password-hash")
