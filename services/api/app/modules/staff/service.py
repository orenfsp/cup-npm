from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.security.passwords import hash_password
from app.db.models import ExpertProfile, StaffUser
from app.db.models.enums import StaffRole
from app.db.repositories.staff_auth import StaffAuthRepository
from app.modules.auth.service import normalize_login


class StaffManagementService:
    """Internal staff lifecycle operations; no HTTP administration is exposed yet."""

    def __init__(self, repository: StaffAuthRepository) -> None:
        self._repository = repository

    async def create_staff_user(
        self,
        *,
        login: str,
        password: str,
        role: StaffRole,
        display_name: str,
    ) -> StaffUser:
        normalized_login = normalize_login(login)
        normalized_display_name = display_name.strip()
        if not normalized_login or not password or not normalized_display_name:
            raise ValidationError("Login, password, and display name are required.")
        if await self._repository.get_staff_by_login(normalized_login) is not None:
            raise ConflictError("A staff user with this login already exists.")

        staff = StaffUser(
            id=uuid4(),
            login=normalized_login,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
            display_name=normalized_display_name,
        )
        try:
            await self._repository.add_staff_user(staff)
            if role is StaffRole.EXPERT:
                await self._repository.add_expert_profile(ExpertProfile(staff_user_id=staff.id))
            await self._repository.commit()
        except IntegrityError as exc:
            await self._repository.rollback()
            raise ConflictError("A staff user with this login already exists.") from exc
        return staff

    async def set_active(self, staff_user_id: UUID, *, is_active: bool) -> StaffUser:
        staff = await self._get_staff(staff_user_id)
        staff.is_active = is_active
        if not is_active:
            await self._repository.revoke_all_sessions(staff.id, revoked_at=datetime.now(UTC))
        await self._repository.commit()
        return staff

    async def change_password(self, staff_user_id: UUID, *, new_password: str) -> None:
        if not new_password:
            raise ValidationError("A new password is required.")
        staff = await self._get_staff(staff_user_id)
        staff.password_hash = hash_password(new_password)
        staff.must_change_password = False
        await self._repository.revoke_all_sessions(staff.id, revoked_at=datetime.now(UTC))
        await self._repository.commit()

    async def _get_staff(self, staff_user_id: UUID) -> StaffUser:
        staff = await self._repository.get_staff_by_id(staff_user_id)
        if staff is None:
            raise NotFoundError("Staff user was not found.")
        return staff
