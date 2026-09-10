import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.core.config import Settings
from app.core.crypto.hmac import refresh_token_digest
from app.core.errors import InfrastructureError, UnauthorizedError, ValidationError
from app.core.security.passwords import hash_password, verify_password
from app.core.security.tokens import AUTHENTICATION_ERROR, AccessTokenService
from app.db.models import StaffSession, StaffUser
from app.db.repositories.staff_auth import StaffAuthRepository
from app.modules.auth.rate_limit import LoginRateLimiter
from app.modules.auth.schemas import StaffProfile

INVALID_CREDENTIALS = "Invalid staff credentials."
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


def normalize_login(login: str) -> str:
    """Apply the same storage and lookup normalization to staff logins."""

    return login.strip().lower()


@dataclass(frozen=True, slots=True)
class AuthenticationResult:
    access_token: str
    access_token_expires_in: int
    refresh_token: str
    staff: StaffProfile


class AuthService:
    def __init__(
        self,
        repository: StaffAuthRepository,
        settings: Settings,
        rate_limiter: LoginRateLimiter,
    ) -> None:
        refresh_secret = settings.refresh_token_hmac_secret
        if refresh_secret is None or not refresh_secret.get_secret_value():
            raise InfrastructureError("Staff refresh sessions are not configured.")
        self._repository = repository
        self._settings = settings
        self._refresh_secret = refresh_secret.get_secret_value()
        self._tokens = AccessTokenService(settings)
        self._rate_limiter = rate_limiter

    async def login(self, *, login: str, password: str, transient_ip: str) -> AuthenticationResult:
        normalized_login = normalize_login(login)
        await self._rate_limiter.check(
            transient_ip=transient_ip,
            normalized_login=normalized_login,
        )
        staff = await self._repository.get_staff_by_login(normalized_login)
        password_hash = (
            staff.password_hash
            if staff is not None and staff.password_hash is not None
            else _DUMMY_PASSWORD_HASH
        )
        valid_password = verify_password(password, password_hash)
        if staff is None or not valid_password or not staff.is_active:
            raise UnauthorizedError(INVALID_CREDENTIALS)

        now = datetime.now(UTC)
        raw_refresh_token = secrets.token_urlsafe(48)
        session = StaffSession(
            id=uuid4(),
            staff_user_id=staff.id,
            refresh_token_digest=self._digest_refresh_token(raw_refresh_token),
            expires_at=now + timedelta(days=self._settings.refresh_session_ttl_days),
            rotation_counter=0,
        )
        staff.last_login_at = now
        await self._repository.add_session(session)
        await self._repository.commit()
        return self._result(staff, session, raw_refresh_token, now=now)

    async def refresh(self, raw_refresh_token: str) -> AuthenticationResult:
        digest = self._digest_refresh_token(raw_refresh_token)
        session = await self._repository.get_session_by_refresh_digest_for_update(digest)
        now = datetime.now(UTC)
        if session is None or session.revoked_at is not None or session.expires_at <= now:
            raise UnauthorizedError(AUTHENTICATION_ERROR)

        staff = await self._repository.get_staff_by_id(session.staff_user_id)
        if staff is None or not staff.is_active:
            session.revoked_at = now
            await self._repository.commit()
            raise UnauthorizedError(AUTHENTICATION_ERROR)

        rotated_refresh_token = secrets.token_urlsafe(48)
        session.refresh_token_digest = self._digest_refresh_token(rotated_refresh_token)
        session.last_used_at = now
        session.rotation_counter += 1
        await self._repository.commit()
        return self._result(staff, session, rotated_refresh_token, now=now)

    async def logout(self, raw_refresh_token: str | None) -> None:
        if not raw_refresh_token:
            return
        digest = self._digest_refresh_token(raw_refresh_token)
        session = await self._repository.get_session_by_refresh_digest_for_update(digest)
        if session is not None and session.revoked_at is None:
            session.revoked_at = datetime.now(UTC)
            await self._repository.commit()

    async def authenticate_access_token(self, token: str) -> StaffUser:
        claims = self._tokens.decode(token)
        session = await self._repository.get_session_by_id(claims.session_id)
        now = datetime.now(UTC)
        if session is None or session.revoked_at is not None or session.expires_at <= now:
            raise UnauthorizedError(AUTHENTICATION_ERROR)
        if session.staff_user_id != claims.staff_user_id:
            raise UnauthorizedError(AUTHENTICATION_ERROR)

        staff = await self._repository.get_staff_by_id(claims.staff_user_id)
        if staff is None or not staff.is_active or staff.role is not claims.role:
            raise UnauthorizedError(AUTHENTICATION_ERROR)
        return staff

    async def change_password(self, staff_user_id: UUID, *, new_password: str) -> None:
        if len(new_password) < 12:
            raise ValidationError("Password must contain at least 12 characters.")
        staff = await self._repository.get_staff_by_id(staff_user_id)
        if staff is None or not staff.is_active:
            raise UnauthorizedError(AUTHENTICATION_ERROR)
        now = datetime.now(UTC)
        staff.password_hash = hash_password(new_password)
        staff.must_change_password = False
        await self._repository.revoke_all_sessions(staff.id, revoked_at=now)
        await self._repository.commit()

    def _digest_refresh_token(self, raw_refresh_token: str) -> bytes:
        return refresh_token_digest(self._refresh_secret, raw_refresh_token)

    def _result(
        self,
        staff: StaffUser,
        session: StaffSession,
        raw_refresh_token: str,
        *,
        now: datetime,
    ) -> AuthenticationResult:
        return AuthenticationResult(
            access_token=self._tokens.issue(
                staff_user_id=staff.id,
                role=staff.role,
                session_id=session.id,
                now=now,
            ),
            access_token_expires_in=self._tokens.lifetime_seconds,
            refresh_token=raw_refresh_token,
            staff=StaffProfile(
                id=staff.id,
                login=staff.login,
                display_name=staff.display_name,
                role=staff.role,
                must_change_password=bool(staff.must_change_password),
            ),
        )
