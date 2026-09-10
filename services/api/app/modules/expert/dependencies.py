from typing import Annotated, cast

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ForbiddenError
from app.db.models import StaffUser
from app.db.repositories.expert import ExpertRepository
from app.db.repositories.operator import OperatorRepository
from app.db.session import get_db_session
from app.modules.auth.dependencies import get_current_staff
from app.modules.auth.policy import AccessPolicy
from app.modules.expert.composer_lock import ComposerLockService
from app.modules.expert.service import ExpertService, ExpertServiceDependencies
from app.modules.routing.service import RoutingService


async def get_current_expert(
    staff: Annotated[StaffUser, Depends(get_current_staff)],
) -> StaffUser:
    if not AccessPolicy.expert_may_use_workspace(staff.role):
        raise ForbiddenError()
    return staff


def get_expert_service(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ExpertService:
    settings = cast(Settings, request.app.state.settings)
    valkey = cast(Redis, request.app.state.valkey)
    return ExpertService(
        ExpertServiceDependencies(
            repository=ExpertRepository(session),
            routing=RoutingService(OperatorRepository(session)),
            composer_locks=ComposerLockService(
                valkey, ttl_seconds=settings.expert_composer_lock_ttl_seconds
            ),
        ),
        settings,
    )
