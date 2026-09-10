from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExpertProfile, StaffSession, StaffUser


class StaffAuthRepository:
    """Concrete persistence operations used by staff authentication services."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_staff_by_login(self, login: str) -> StaffUser | None:
        return await self._session.scalar(select(StaffUser).where(StaffUser.login == login))

    async def get_staff_by_id(self, staff_user_id: UUID) -> StaffUser | None:
        return await self._session.get(StaffUser, staff_user_id)

    async def add_staff_user(self, staff_user: StaffUser) -> None:
        self._session.add(staff_user)
        await self._session.flush()

    async def get_expert_profile(self, staff_user_id: UUID) -> ExpertProfile | None:
        return await self._session.get(ExpertProfile, staff_user_id)

    async def add_expert_profile(self, profile: ExpertProfile) -> None:
        self._session.add(profile)
        await self._session.flush()

    async def add_session(self, staff_session: StaffSession) -> None:
        self._session.add(staff_session)
        await self._session.flush()

    async def get_session_by_id(self, session_id: UUID) -> StaffSession | None:
        return await self._session.get(StaffSession, session_id)

    async def get_session_by_refresh_digest_for_update(self, digest: bytes) -> StaffSession | None:
        statement = (
            select(StaffSession)
            .where(StaffSession.refresh_token_digest == digest)
            .with_for_update()
        )
        return await self._session.scalar(statement)

    async def revoke_all_sessions(self, staff_user_id: UUID, *, revoked_at: datetime) -> None:
        await self._session.execute(
            update(StaffSession)
            .where(
                StaffSession.staff_user_id == staff_user_id,
                StaffSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
