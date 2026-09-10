from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CrisisRule


class CrisisRuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self) -> list[CrisisRule]:
        result = await self._session.scalars(
            select(CrisisRule)
            .where(CrisisRule.is_active.is_(True))
            .order_by(CrisisRule.sort_order, CrisisRule.id)
        )
        return list(result)

    async def get_by_normalized_phrase(self, phrase: str) -> CrisisRule | None:
        return await self._session.scalar(
            select(CrisisRule).where(CrisisRule.normalized_phrase == phrase)
        )

    async def add(self, rule: CrisisRule) -> None:
        self._session.add(rule)
        await self._session.flush()

    async def commit(self) -> None:
        await self._session.commit()
