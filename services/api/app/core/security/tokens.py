from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.config import Settings
from app.core.errors import InfrastructureError, UnauthorizedError
from app.db.models.enums import StaffRole

AUTHENTICATION_ERROR = "Invalid or expired authentication."


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    staff_user_id: UUID
    session_id: UUID
    role: StaffRole


class AccessTokenService:
    """Issue and validate narrowly scoped staff access JWTs."""

    algorithm = "HS256"

    def __init__(self, settings: Settings) -> None:
        secret = settings.jwt_secret
        if secret is None or not secret.get_secret_value():
            raise InfrastructureError("Staff authentication is not configured.")
        self._secret = secret.get_secret_value()
        self._issuer = settings.jwt_issuer
        self._audience = settings.jwt_audience
        self._ttl = timedelta(minutes=settings.access_token_ttl_minutes)

    @property
    def lifetime_seconds(self) -> int:
        return int(self._ttl.total_seconds())

    def issue(
        self,
        *,
        staff_user_id: UUID,
        role: StaffRole,
        session_id: UUID,
        now: datetime | None = None,
    ) -> str:
        issued_at = now or datetime.now(UTC)
        return jwt.encode(
            {
                "sub": str(staff_user_id),
                "role": role.value,
                "sid": str(session_id),
                "iat": issued_at,
                "exp": issued_at + self._ttl,
                "iss": self._issuer,
                "aud": self._audience,
            },
            self._secret,
            algorithm=self.algorithm,
        )

    def decode(self, token: str) -> AccessTokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self.algorithm],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["sub", "role", "sid", "iat", "exp", "iss", "aud"]},
            )
            return AccessTokenClaims(
                staff_user_id=UUID(payload["sub"]),
                session_id=UUID(payload["sid"]),
                role=StaffRole(payload["role"]),
            )
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
            raise UnauthorizedError(
                AUTHENTICATION_ERROR,
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
