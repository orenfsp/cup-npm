from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.config import Settings
from app.core.errors import InfrastructureError, UnauthorizedError

APPEAL_ACCESS_SCOPE = "appeal:read-write"
APPEAL_ACCESS_ERROR = "Appeal access is invalid or expired."


@dataclass(frozen=True, slots=True)
class AppealAccessClaims:
    appeal_id: UUID


class AppealAccessTokenService:
    """Issue stateless, short-lived capabilities scoped to exactly one appeal."""

    algorithm = "HS256"

    def __init__(self, settings: Settings) -> None:
        secret = settings.applicant_access_jwt_secret
        if secret is None or not secret.get_secret_value():
            raise InfrastructureError("Anonymous appeal access is not configured.")
        self._secret = secret.get_secret_value()
        self._issuer = settings.applicant_access_jwt_issuer
        self._audience = settings.applicant_access_jwt_audience
        self._ttl = timedelta(minutes=settings.applicant_access_ttl_minutes)

    def issue(self, appeal_id: UUID, *, now: datetime | None = None) -> str:
        issued_at = now or datetime.now(UTC)
        return jwt.encode(
            {
                "sub": str(appeal_id),
                "scope": APPEAL_ACCESS_SCOPE,
                "iat": issued_at,
                "exp": issued_at + self._ttl,
                "iss": self._issuer,
                "aud": self._audience,
            },
            self._secret,
            algorithm=self.algorithm,
        )

    def decode(self, token: str) -> AppealAccessClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self.algorithm],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["sub", "scope", "iat", "exp", "iss", "aud"]},
            )
            if payload["scope"] != APPEAL_ACCESS_SCOPE:
                raise ValueError("Invalid scope")
            return AppealAccessClaims(appeal_id=UUID(payload["sub"]))
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
            raise UnauthorizedError(APPEAL_ACCESS_ERROR) from exc
