from collections.abc import Callable
from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.db.models import StaffUser
from app.db.models.enums import StaffRole
from app.db.repositories.staff_auth import StaffAuthRepository
from app.db.session import get_db_session
from app.modules.auth.rate_limit import LoginRateLimiter
from app.modules.auth.service import AuthService

bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_service(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthService:
    settings = cast(Settings, request.app.state.settings)
    valkey = cast(Redis, request.app.state.valkey)
    return AuthService(
        StaffAuthRepository(session),
        settings,
        LoginRateLimiter(valkey, settings),
    )


async def get_authenticated_staff(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> StaffUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError(headers={"WWW-Authenticate": "Bearer"})
    return await auth_service.authenticate_access_token(credentials.credentials)


async def get_current_staff(
    staff: Annotated[StaffUser, Depends(get_authenticated_staff)],
) -> StaffUser:
    if staff.must_change_password:
        raise ForbiddenError("Password change is required.")
    return staff


def require_any_role(*roles: StaffRole) -> Callable[..., StaffUser]:
    allowed_roles = frozenset(roles)

    async def role_dependency(
        staff: Annotated[StaffUser, Depends(get_current_staff)],
    ) -> StaffUser:
        if staff.role not in allowed_roles:
            raise ForbiddenError()
        return staff

    return role_dependency


def require_role(role: StaffRole) -> Callable[..., StaffUser]:
    return require_any_role(role)
