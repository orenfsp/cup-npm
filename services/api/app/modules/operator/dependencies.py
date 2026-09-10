from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ForbiddenError
from app.db.models import StaffUser
from app.db.repositories.operator import OperatorRepository
from app.db.session import get_db_session
from app.modules.auth.dependencies import get_current_staff
from app.modules.auth.policy import AccessPolicy
from app.modules.operator.service import OperatorService


async def get_current_operator(
    staff: Annotated[StaffUser, Depends(get_current_staff)],
) -> StaffUser:
    if not AccessPolicy.operator_may_triage(staff.role):
        raise ForbiddenError()
    return staff


def get_operator_service(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OperatorService:
    settings = cast(Settings, request.app.state.settings)
    return OperatorService(OperatorRepository(session), settings)
