from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, Response

from app.core.config import Settings
from app.core.errors import UnauthorizedError
from app.db.models import StaffUser
from app.modules.auth.dependencies import get_auth_service, get_authenticated_staff
from app.modules.auth.schemas import (
    AccessTokenResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    LogoutResponse,
    StaffProfile,
)
from app.modules.auth.service import AuthenticationResult, AuthService

router = APIRouter(prefix="/auth", tags=["staff-auth"])


def _set_refresh_cookie(
    response: Response,
    *,
    settings: Settings,
    refresh_token: str,
) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_session_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="lax",
        path=f"{settings.api_prefix}/auth",
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="lax",
        path=f"{settings.api_prefix}/auth",
    )


def _prevent_caching(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def _token_response(result: AuthenticationResult) -> AccessTokenResponse:
    return AccessTokenResponse(
        access_token=result.access_token,
        expires_in=result.access_token_expires_in,
        staff=result.staff,
    )


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AccessTokenResponse:
    client_ip = request.client.host if request.client is not None else "unknown"
    result = await auth_service.login(
        login=payload.login,
        password=payload.password.get_secret_value(),
        transient_ip=client_ip,
    )
    settings = cast(Settings, request.app.state.settings)
    _set_refresh_cookie(response, settings=settings, refresh_token=result.refresh_token)
    _prevent_caching(response)
    return _token_response(result)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AccessTokenResponse:
    settings = cast(Settings, request.app.state.settings)
    raw_token = request.cookies.get(settings.refresh_cookie_name)
    if not raw_token:
        raise UnauthorizedError("Invalid or expired authentication.")
    result = await auth_service.refresh(raw_token)
    _set_refresh_cookie(response, settings=settings, refresh_token=result.refresh_token)
    _prevent_caching(response)
    return _token_response(result)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> LogoutResponse:
    settings = cast(Settings, request.app.state.settings)
    raw_token = request.cookies.get(settings.refresh_cookie_name)
    await auth_service.logout(raw_token)
    _clear_refresh_cookie(response, settings)
    _prevent_caching(response)
    return LogoutResponse()


@router.get("/me", response_model=StaffProfile)
async def me(
    response: Response,
    staff: Annotated[StaffUser, Depends(get_authenticated_staff)],
) -> StaffProfile:
    _prevent_caching(response)
    return StaffProfile(
        id=staff.id,
        login=staff.login,
        display_name=staff.display_name,
        role=staff.role,
        must_change_password=bool(staff.must_change_password),
    )


@router.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    staff: Annotated[StaffUser, Depends(get_authenticated_staff)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> ChangePasswordResponse:
    await auth_service.change_password(
        staff.id,
        new_password=payload.password.get_secret_value(),
    )
    settings = cast(Settings, request.app.state.settings)
    _clear_refresh_cookie(response, settings)
    _prevent_caching(response)
    return ChangePasswordResponse()
