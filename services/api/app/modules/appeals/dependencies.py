from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import UnauthorizedError
from app.db.repositories.crisis_rules import CrisisRuleRepository
from app.db.repositories.public_appeals import PublicAppealRepository
from app.db.session import get_db_session
from app.modules.appeals.rate_limit import PublicAppealRateLimiter
from app.modules.appeals.service import PublicAppealService
from app.modules.attachments.service import AttachmentService
from app.modules.crisis.service import CrisisRuleService


def get_public_appeal_service(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PublicAppealService:
    settings = cast(Settings, request.app.state.settings)
    return PublicAppealService(
        PublicAppealRepository(session),
        settings,
        CrisisRuleService(CrisisRuleRepository(session)),
    )


def get_public_appeal_rate_limiter(request: Request) -> PublicAppealRateLimiter:
    settings = cast(Settings, request.app.state.settings)
    valkey = cast(Redis, request.app.state.valkey)
    return PublicAppealRateLimiter(valkey, settings)


def get_attachment_service(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AttachmentService:
    settings = cast(Settings, request.app.state.settings)
    return AttachmentService(PublicAppealRepository(session), settings)


def get_current_appeal_id(
    request: Request,
    service: Annotated[PublicAppealService, Depends(get_public_appeal_service)],
) -> UUID:
    settings = cast(Settings, request.app.state.settings)
    token = request.cookies.get(settings.applicant_access_cookie_name)
    if not token:
        raise UnauthorizedError("Appeal access is required.")
    return service.decode_access_token(token)
