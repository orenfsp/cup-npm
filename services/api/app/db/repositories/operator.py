from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.models import (
    Appeal,
    AppealContent,
    AppealIntakeAnswer,
    AppealParticipant,
    AppealRejection,
    AppealReturnExplanation,
    AssignmentHistory,
    Attachment,
    AuditLog,
    Category,
    CategoryGroupRule,
    CrisisContact,
    ExpertGroupMembership,
    ExpertProfile,
    SpecialistGroup,
    StaffComplaint,
    StaffUser,
    StatusHistory,
    TransferRequest,
)
from app.db.models.enums import (
    AppealParticipantRole,
    AppealPriority,
    AppealStatus,
    StaffRole,
    TransferRequestStatus,
)

ACTIVE_APPEAL_STATUSES = (
    AppealStatus.NEW,
    AppealStatus.ASSIGNED,
    AppealStatus.IN_PROGRESS,
    AppealStatus.NEEDS_CLARIFICATION,
    AppealStatus.ANSWER_READY,
    AppealStatus.RETURNED,
)
QUEUE_STATUSES = (AppealStatus.NEW, AppealStatus.RETURNED)


@dataclass(frozen=True, slots=True)
class QueueRecord:
    appeal: Appeal
    category: Category | None


@dataclass(frozen=True, slots=True)
class OperatorDetailRecord:
    appeal: Appeal
    category: Category | None
    suggested_category: Category | None
    content: AppealContent | None
    intake: AppealIntakeAnswer | None
    assigned_expert: StaffUser | None
    attachments: list[Attachment]
    status_history: list[StatusHistory]
    assignment_history: list[AssignmentHistory]
    return_explanations: list[AppealReturnExplanation] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class OperatorTransferRecord:
    transfer: TransferRequest
    appeal: Appeal
    requester: StaffUser
    target: StaffUser | None


@dataclass(frozen=True, slots=True)
class RoutingCandidateRecord:
    staff: StaffUser
    profile: ExpertProfile
    group: SpecialistGroup
    current_load: int


class OperatorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _queue_statement(self) -> Select[tuple[Appeal, Category | None]]:
        return select(Appeal, Category).outerjoin(Category, Appeal.category_id == Category.id)

    async def list_queue(
        self,
        *,
        status: AppealStatus | None,
        priority: AppealPriority | None,
        category_id: UUID | None,
        crisis: bool | None,
        assigned: bool | None,
        offset: int,
        limit: int,
    ) -> tuple[list[QueueRecord], int]:
        statement = self._queue_statement()
        conditions = []
        if status is None:
            conditions.append(Appeal.status.in_(QUEUE_STATUSES))
        else:
            conditions.append(Appeal.status == status)
        if priority is not None:
            conditions.append(Appeal.priority == priority)
        if category_id is not None:
            conditions.append(Appeal.category_id == category_id)
        if crisis is not None:
            conditions.append(Appeal.crisis_flag.is_(crisis))
        if assigned is not None:
            conditions.append(
                Appeal.assigned_expert_id.is_not(None)
                if assigned
                else Appeal.assigned_expert_id.is_(None)
            )
        statement = statement.where(*conditions)
        total = int(
            await self._session.scalar(
                select(func.count()).select_from(statement.order_by(None).subquery())
            )
            or 0
        )
        priority_order = case(
            (Appeal.priority == AppealPriority.URGENT, 0),
            (Appeal.priority == AppealPriority.STANDARD, 1),
            else_=2,
        )
        rows = (
            await self._session.execute(
                statement.order_by(
                    Appeal.crisis_flag.desc(), priority_order, Appeal.created_at, Appeal.id
                )
                .offset(offset)
                .limit(limit)
            )
        ).all()
        return [QueueRecord(row[0], row[1]) for row in rows], total

    async def queue_counter_rows(self) -> list[Appeal]:
        result = await self._session.scalars(
            select(Appeal).where(Appeal.status.in_(QUEUE_STATUSES))
        )
        return list(result)

    async def get_detail(self, appeal_id: UUID) -> OperatorDetailRecord | None:
        category_alias = Category
        row = (
            await self._session.execute(
                select(Appeal, category_alias, AppealContent, AppealIntakeAnswer, StaffUser)
                .outerjoin(category_alias, Appeal.category_id == category_alias.id)
                .outerjoin(AppealContent, AppealContent.appeal_id == Appeal.id)
                .outerjoin(AppealIntakeAnswer, AppealIntakeAnswer.appeal_id == Appeal.id)
                .outerjoin(StaffUser, StaffUser.id == Appeal.assigned_expert_id)
                .where(Appeal.id == appeal_id)
            )
        ).one_or_none()
        if row is None:
            return None
        appeal, category, content, intake, assigned_expert = row
        suggested = (
            await self._session.get(Category, appeal.suggested_category_id)
            if appeal.suggested_category_id
            else None
        )
        attachments = list(
            await self._session.scalars(
                select(Attachment)
                .where(Attachment.appeal_id == appeal_id)
                .order_by(Attachment.created_at, Attachment.id)
            )
        )
        status_history = list(
            await self._session.scalars(
                select(StatusHistory)
                .where(StatusHistory.appeal_id == appeal_id)
                .order_by(StatusHistory.created_at, StatusHistory.id)
            )
        )
        assignment_history = list(
            await self._session.scalars(
                select(AssignmentHistory)
                .where(AssignmentHistory.appeal_id == appeal_id)
                .order_by(AssignmentHistory.created_at, AssignmentHistory.id)
            )
        )
        return_explanations = list(
            await self._session.scalars(
                select(AppealReturnExplanation)
                .where(AppealReturnExplanation.appeal_id == appeal_id)
                .order_by(
                    AppealReturnExplanation.return_number,
                    AppealReturnExplanation.created_at,
                )
            )
        )
        return OperatorDetailRecord(
            appeal,
            category,
            suggested,
            content,
            intake,
            assigned_expert,
            attachments,
            status_history,
            assignment_history,
            return_explanations,
        )

    async def get_appeal_for_update(self, appeal_id: UUID) -> Appeal | None:
        return await self._session.scalar(
            select(Appeal).where(Appeal.id == appeal_id).with_for_update()
        )

    async def get_category(self, category_id: UUID) -> Category | None:
        return await self._session.get(Category, category_id)

    async def list_active_categories(self) -> list[Category]:
        return list(
            await self._session.scalars(
                select(Category)
                .where(Category.is_active.is_(True))
                .order_by(Category.sort_order, Category.name)
            )
        )

    async def routing_candidates(self, category_id: UUID) -> list[RoutingCandidateRecord]:
        active_load = (
            select(func.count(func.distinct(Appeal.id)))
            .join(AppealParticipant, AppealParticipant.appeal_id == Appeal.id)
            .where(
                AppealParticipant.staff_user_id == ExpertProfile.staff_user_id,
                AppealParticipant.is_active.is_(True),
                Appeal.status.in_(ACTIVE_APPEAL_STATUSES),
            )
            .correlate(ExpertProfile)
            .scalar_subquery()
        )
        rows = (
            await self._session.execute(
                select(StaffUser, ExpertProfile, SpecialistGroup, active_load.label("load"))
                .join(ExpertProfile, ExpertProfile.staff_user_id == StaffUser.id)
                .join(
                    ExpertGroupMembership,
                    ExpertGroupMembership.expert_id == ExpertProfile.staff_user_id,
                )
                .join(
                    SpecialistGroup,
                    SpecialistGroup.id == ExpertGroupMembership.specialist_group_id,
                )
                .join(
                    CategoryGroupRule,
                    CategoryGroupRule.specialist_group_id == SpecialistGroup.id,
                )
                .where(
                    CategoryGroupRule.category_id == category_id,
                    StaffUser.role == StaffRole.EXPERT,
                    StaffUser.is_active.is_(True),
                    SpecialistGroup.is_active.is_(True),
                )
                .order_by(StaffUser.display_name, StaffUser.id, SpecialistGroup.name)
            )
        ).all()
        return [RoutingCandidateRecord(row[0], row[1], row[2], int(row[3])) for row in rows]

    async def current_primary(self, appeal_id: UUID) -> AppealParticipant | None:
        return await self._session.scalar(
            select(AppealParticipant).where(
                AppealParticipant.appeal_id == appeal_id,
                AppealParticipant.participant_role == AppealParticipantRole.PRIMARY,
                AppealParticipant.is_active.is_(True),
            )
        )

    async def get_staff(self, staff_id: UUID) -> StaffUser | None:
        # Serialize assignments targeting the same expert so the capacity check that
        # follows observes any assignment committed by the previous operator.
        return await self._session.scalar(
            select(StaffUser).where(StaffUser.id == staff_id).with_for_update()
        )

    async def get_attachment(self, appeal_id: UUID, attachment_id: UUID) -> Attachment | None:
        return await self._session.scalar(
            select(Attachment).where(
                Attachment.id == attachment_id, Attachment.appeal_id == appeal_id
            )
        )

    async def get_crisis_contact(self, appeal_id: UUID) -> CrisisContact | None:
        return await self._session.get(CrisisContact, appeal_id)

    async def list_pending_transfers(self) -> list[OperatorTransferRecord]:
        requester = aliased(StaffUser, name="requester")
        target = aliased(StaffUser, name="target")
        rows = (
            await self._session.execute(
                select(TransferRequest, Appeal, requester, target)
                .join(Appeal, Appeal.id == TransferRequest.appeal_id)
                .join(requester, requester.id == TransferRequest.requested_by_staff_user_id)
                .outerjoin(target, target.id == TransferRequest.requested_target_staff_user_id)
                .where(TransferRequest.status == TransferRequestStatus.PENDING)
                .order_by(TransferRequest.created_at, TransferRequest.id)
            )
        ).all()
        return [OperatorTransferRecord(row[0], row[1], row[2], row[3]) for row in rows]

    async def get_transfer_for_update(self, transfer_id: UUID) -> TransferRequest | None:
        return await self._session.scalar(
            select(TransferRequest).where(TransferRequest.id == transfer_id).with_for_update()
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

    async def list_complaints(self, appeal_id: UUID) -> list[StaffComplaint]:
        return list(
            await self._session.scalars(
                select(StaffComplaint)
                .where(StaffComplaint.appeal_id == appeal_id)
                .order_by(StaffComplaint.created_at, StaffComplaint.id)
            )
        )

    async def upsert_rejection(self, rejection: AppealRejection) -> None:
        existing = await self._session.get(AppealRejection, rejection.appeal_id)
        if existing is None:
            self._session.add(rejection)
        else:
            existing.kind = rejection.kind
            existing.encrypted_reason = rejection.encrypted_reason
            existing.key_version = rejection.key_version
        await self._session.flush()

    async def add_all(self, records: list[object]) -> None:
        self._session.add_all(records)
        await self._session.flush()

    async def add_audit(self, audit: AuditLog) -> None:
        self._session.add(audit)
        await self._session.flush()

    async def commit(self) -> None:
        await self._session.commit()

    async def flush(self) -> None:
        await self._session.flush()

    async def rollback(self) -> None:
        await self._session.rollback()
