import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.api.router import api_router, root_router
from app.core.config import AppEnvironment, Settings, get_settings
from app.core.errors.handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.core.security.headers import SecurityHeadersMiddleware
from app.core.valkey import create_valkey_client
from app.db import Database, create_database

logger = logging.getLogger(__name__)


def _sensitive_values(settings: Settings) -> list[str]:
    values = [settings.database_url, settings.valkey_url]
    for secret in (
        settings.jwt_secret,
        settings.track_hmac_secret,
        settings.rate_limit_hmac_secret,
        settings.refresh_token_hmac_secret,
        settings.applicant_access_jwt_secret,
        settings.content_encryption_key,
        settings.demo_operator_password,
        settings.demo_expert_password,
        settings.demo_psychologist_password,
        settings.demo_lawyer_password,
        settings.demo_social_password,
        settings.demo_conflict_password,
        settings.demo_admin_password,
        settings.smtp_password,
    ):
        if secret is not None:
            values.append(secret.get_secret_value())
    return values


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = cast(Settings, app.state.settings)
    database = create_database(settings.database_url)
    valkey = create_valkey_client(settings.valkey_url)
    app.state.database = database
    app.state.valkey = valkey

    try:
        await asyncio.wait_for(valkey.ping(), timeout=settings.healthcheck_timeout_seconds)
    except Exception as exc:
        # Startup remains available so the readiness endpoint can report the outage.
        logger.warning("Valkey startup check failed type=%s", type(exc).__name__)

    logger.info("Application startup complete")
    try:
        yield
    finally:
        await _close_resources(valkey, database)
        logger.info("Application shutdown complete")


async def _close_resources(valkey: Redis, database: Database) -> None:
    try:
        await valkey.aclose()
    except Exception as exc:
        logger.warning("Valkey shutdown failed type=%s", type(exc).__name__)
    finally:
        await database.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(
        resolved_settings.log_level,
        sensitive_values=_sensitive_values(resolved_settings),
    )

    is_production = resolved_settings.app_env is AppEnvironment.PRODUCTION
    application = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.api_version,
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings

    register_exception_handlers(application)
    application.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=is_production,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Authorization", "Content-Type"],
    )
    application.include_router(root_router)
    application.include_router(api_router, prefix=resolved_settings.api_prefix)
    return application


app = create_app()
