from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Appeal,
    AppealContent,
    AppealIntakeAnswer,
    AppealMessage,
    AppealParticipant,
    Attachment,
    Category,
    InternalNote,
    StaffUser,
    TransferRequest,
)
from app.db.models.enums import (
    AppealParticipantRole,
    AppealPriority,
    AppealStatus,
    TransferRequestStatus,
)

EXPERT_QUEUE_STATUSES = (
    AppealStatus.ASSIGNED,
    AppealStatus.IN_PROGRESS,
    AppealStatus.NEEDS_CLARIFICATION,
    AppealStatus.ANSWER_READY,
)


@dataclass(frozen=True, slots=True)
class ExpertQueueRecord:
    appeal: Appeal
    category: Category | None


@dataclass(frozen=True, slots=True)
class ExpertDetailRecord:
    appeal: Appeal
    category: Category | None
    content: AppealContent | None
    intake: AppealIntakeAnswer | None
    attachments: list[Attachment]
    messages: list[tuple[AppealMessage, StaffUser | None]]
    notes: list[tuple[InternalNote, StaffUser]]
    participants: list[tuple[AppealParticipant, StaffUser]]
    transfers: list[TransferRequest]


class ExpertRepository:
    """Appeal reads are always constrained by an active participant row."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_queue(
        self,
        expert_id: UUID,
        *,
        status: AppealStatus | None,
        priority: AppealPriority | None,
        category_id: UUID | None,
        offset: int,
        limit: int,
    ) -> tuple[list[ExpertQueueRecord], int]:
        conditions = [
            AppealParticipant.staff_user_id == expert_id,
            AppealParticipant.is_active.is_(True),
        ]
        conditions.append(
            Appeal.status == status
            if status is not None
            else Appeal.status.in_(EXPERT_QUEUE_STATUSES)
        )
        if priority is not None:
            conditions.append(Appeal.priority == priority)
        if category_id is not None:
            conditions.append(Appeal.category_id == category_id)
        statement = (
            select(Appeal, Category)
            .join(AppealParticipant, AppealParticipant.appeal_id == Appeal.id)
            .outerjoin(Category, Appeal.category_id == Category.id)
            .where(*conditions)
        )
        total = int(
            await self._session.scalar(
                select(func.count()).select_from(statement.order_by(None).subquery())
            )
            or 0
        )
        attention_rank = case(
            ((Appeal.crisis_flag.is_(True)) | (Appeal.priority == AppealPriority.URGENT), 0),
            else_=1,
        )
        action_rank = case(
            (Appeal.status == AppealStatus.ASSIGNED, 0),
            (Appeal.status == AppealStatus.IN_PROGRESS, 1),
            (Appeal.status == AppealStatus.NEEDS_CLARIFICATION, 2),
            else_=3,
        )
        rows = (
            await self._session.execute(
                statement.order_by(attention_rank, action_rank, Appeal.created_at, Appeal.id)
                .offset(offset)
                .limit(limit)
            )
        ).all()
        return [ExpertQueueRecord(row[0], row[1]) for row in rows], total

    async def get_appeal_for_participant(
        self, appeal_id: UUID, expert_id: UUID, *, for_update: bool = False
    ) -> Appeal | None:
        statement = (
            select(Appeal)
            .join(AppealParticipant, AppealParticipant.appeal_id == Appeal.id)
            .where(
                Appeal.id == appeal_id,
                AppealParticipant.staff_user_id == expert_id,
                AppealParticipant.is_active.is_(True),
            )
        )
        if for_update:
            statement = statement.with_for_update(of=Appeal)
        return await self._session.scalar(statement)

    async def get_detail(self, appeal_id: UUID, expert_id: UUID) -> ExpertDetailRecord | None:
        row = (
            await self._session.execute(
                select(Appeal, Category, AppealContent, AppealIntakeAnswer)
                .join(AppealParticipant, AppealParticipant.appeal_id == Appeal.id)
                .outerjoin(Category, Appeal.category_id == Category.id)
                .outerjoin(AppealContent, AppealContent.appeal_id == Appeal.id)
                .outerjoin(AppealIntakeAnswer, AppealIntakeAnswer.appeal_id == Appeal.id)
                .where(
                    Appeal.id == appeal_id,
                    AppealParticipant.staff_user_id == expert_id,
                    AppealParticipant.is_active.is_(True),
                )
            )
        ).one_or_none()
        if row is None:
            return None
        appeal, category, content, intake = row
        attachments = list(
            await self._session.scalars(
                select(Attachment)
                .where(Attachment.appeal_id == appeal_id)
                .order_by(Attachment.created_at, Attachment.id)
            )
        )
        messages = list(
            (
                await self._session.execute(
                    select(AppealMessage, StaffUser)
                    .outerjoin(StaffUser, StaffUser.id == AppealMessage.author_staff_user_id)
                    .where(AppealMessage.appeal_id == appeal_id)
                    .order_by(AppealMessage.created_at, AppealMessage.id)
                )
            ).all()
        )
        notes = list(
            (
                await self._session.execute(
                    select(InternalNote, StaffUser)
                    .join(StaffUser, StaffUser.id == InternalNote.author_staff_user_id)
                    .where(InternalNote.appeal_id == appeal_id)
                    .order_by(InternalNote.created_at, InternalNote.id)
                )
            ).all()
        )
        participants = list(
            (
                await self._session.execute(
                    select(AppealParticipant, StaffUser)
                    .join(StaffUser, StaffUser.id == AppealParticipant.staff_user_id)
                    .where(
                        AppealParticipant.appeal_id == appeal_id,
                        AppealParticipant.is_active.is_(True),
                    )
                    .order_by(AppealParticipant.participant_role, AppealParticipant.joined_at)
                )
            ).all()
        )
        transfers = list(
            await self._session.scalars(
                select(TransferRequest)
                .where(TransferRequest.appeal_id == appeal_id)
                .order_by(TransferRequest.created_at.desc(), TransferRequest.id.desc())
            )
        )
        return ExpertDetailRecord(
            appeal,
            category,
            content,
            intake,
            attachments,
            messages,
            notes,
            participants,
            transfers,
        )

    async def list_notes_for_participant(
        self, appeal_id: UUID, expert_id: UUID
    ) -> list[tuple[InternalNote, StaffUser]] | None:
        appeal = await self.get_appeal_for_participant(appeal_id, expert_id)
        if appeal is None:
            return None
        return list(
            (
                await self._session.execute(
                    select(InternalNote, StaffUser)
                    .join(StaffUser, StaffUser.id == InternalNote.author_staff_user_id)
                    .where(InternalNote.appeal_id == appeal_id)
                    .order_by(InternalNote.created_at, InternalNote.id)
                )
            ).all()
        )

    async def get_attachment_for_participant(
        self, appeal_id: UUID, attachment_id: UUID, expert_id: UUID
    ) -> Attachment | None:
        return await self._session.scalar(
            select(Attachment)
            .join(AppealParticipant, AppealParticipant.appeal_id == Attachment.appeal_id)
            .where(
                Attachment.id == attachment_id,
                Attachment.appeal_id == appeal_id,
                AppealParticipant.staff_user_id == expert_id,
                AppealParticipant.is_active.is_(True),
            )
        )

    async def current_primary(self, appeal_id: UUID) -> AppealParticipant | None:
        return await self._session.scalar(
            select(AppealParticipant).where(
                AppealParticipant.appeal_id == appeal_id,
                AppealParticipant.participant_role == AppealParticipantRole.PRIMARY,
                AppealParticipant.is_active.is_(True),
            )
        )

    async def active_participant(
        self, appeal_id: UUID, staff_user_id: UUID
    ) -> AppealParticipant | None:
        return await self._session.scalar(
            select(AppealParticipant).where(
                AppealParticipant.appeal_id == appeal_id,
                AppealParticipant.staff_user_id == staff_user_id,
                AppealParticipant.is_active.is_(True),
            )
        )

    async def get_staff_for_update(self, staff_user_id: UUID) -> StaffUser | None:
        return await self._session.scalar(
            select(StaffUser).where(StaffUser.id == staff_user_id).with_for_update()
        )

    async def has_pending_transfer(self, appeal_id: UUID) -> bool:
        return (
            await self._session.scalar(
                select(TransferRequest.id)
                .where(
                    TransferRequest.appeal_id == appeal_id,
                    TransferRequest.status == TransferRequestStatus.PENDING,
                )
                .limit(1)
            )
            is not None
        )

    async def add_all(self, records: list[object]) -> None:
        self._session.add_all(records)
        await self._session.flush()

    async def commit(self) -> None:
        await self._session.commit()
