import asyncio
from collections.abc import Awaitable, Callable
from http import HTTPStatus

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.config import Settings
from app.modules.admin.router import router as admin_router
from app.modules.admin.router import setup_router as staff_setup_router
from app.modules.appeals.router import router as public_appeals_router
from app.modules.auth.router import router as auth_router
from app.modules.expert.router import router as expert_router
from app.modules.operator.router import router as operator_router


class BasicHealthResponse(BaseModel):
    status: str


class MetaResponse(BaseModel):
    application: str
    environment: str
    api_version: str


class ReadinessServices(BaseModel):
    application: str
    database: str
    valkey: str


class ReadinessResponse(BaseModel):
    status: str
    services: ReadinessServices


root_router = APIRouter()
api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(staff_setup_router)
api_router.include_router(public_appeals_router)
api_router.include_router(operator_router)
api_router.include_router(expert_router)
api_router.include_router(admin_router)


@root_router.get("/health", response_model=BasicHealthResponse, tags=["health"])
async def health() -> BasicHealthResponse:
    return BasicHealthResponse(status="ok")


@api_router.get("/meta", response_model=MetaResponse, tags=["meta"])
async def meta(request: Request) -> MetaResponse:
    settings: Settings = request.app.state.settings
    return MetaResponse(
        application=settings.app_name,
        environment=settings.app_env.value,
        api_version=settings.api_version,
    )


async def _check_service(
    check: Callable[[], Awaitable[object]] | None, *, timeout_seconds: float
) -> bool:
    if check is None:
        return False
    try:
        result = await asyncio.wait_for(check(), timeout=timeout_seconds)
    except Exception:
        return False
    return bool(result)


@api_router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={HTTPStatus.SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
    tags=["health"],
)
async def readiness(request: Request) -> JSONResponse:
    settings: Settings = request.app.state.settings
    database = getattr(request.app.state, "database", None)
    valkey = getattr(request.app.state, "valkey", None)

    database_ok, valkey_ok = await asyncio.gather(
        _check_service(
            getattr(database, "is_healthy", None),
            timeout_seconds=settings.healthcheck_timeout_seconds,
        ),
        _check_service(
            getattr(valkey, "ping", None),
            timeout_seconds=settings.healthcheck_timeout_seconds,
        ),
    )
    is_ready = database_ok and valkey_ok
    payload = ReadinessResponse(
        status="ok" if is_ready else "unavailable",
        services=ReadinessServices(
            application="ok",
            database="ok" if database_ok else "unavailable",
            valkey="ok" if valkey_ok else "unavailable",
        ),
    )
    return JSONResponse(
        status_code=HTTPStatus.OK if is_ready else HTTPStatus.SERVICE_UNAVAILABLE,
        content=payload.model_dump(),
    )
