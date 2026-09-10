from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.email import SMTPMailer
from app.db.models import StaffUser
from app.db.models.enums import StaffRole
from app.db.repositories.admin import AdminRepository
from app.db.session import get_db_session
from app.modules.admin.service import AdminService
from app.modules.auth.dependencies import require_role


def get_admin_service(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminService:
    settings = cast(Settings, request.app.state.settings)
    return AdminService(AdminRepository(session), settings, SMTPMailer(settings))


get_current_admin = require_role(StaffRole.ADMIN)
CurrentAdmin = Annotated[StaffUser, Depends(get_current_admin)]
AdminServiceDependency = Annotated[AdminService, Depends(get_admin_service)]
