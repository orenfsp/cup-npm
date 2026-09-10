from datetime import datetime
from uuid import UUID

from sqlalchemy import Date, and_, cast, delete, extract, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Appeal,
    AppealParticipant,
    ApplicantTypeConfig,
    AuditLog,
    Category,
    CategoryGroupRule,
    CategoryIntakeQuestion,
    CrisisRule,
    CrisisSupportResource,
    ExpertGroupMembership,
    ExpertProfile,
    IntakeQuestion,
    SpecialistGroup,
    StaffInvitation,
    StaffSession,
    StaffUser,
)
from app.db.models.enums import AppealParticipantRole, AppealStatus, StaffRole

ACTIVE_WORKLOAD_STATUSES = (
    AppealStatus.ASSIGNED,
    AppealStatus.IN_PROGRESS,
    AppealStatus.NEEDS_CLARIFICATION,
    AppealStatus.ANSWER_READY,
)


class AdminRepository:
    """Concrete persistence operations for non-sensitive administrator configuration."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_staff(self) -> list[StaffUser]:
        return list(await self._session.scalars(select(StaffUser).order_by(StaffUser.login)))

    async def get_staff(self, staff_id: UUID) -> StaffUser | None:
        return await self._session.get(StaffUser, staff_id)

    async def get_staff_by_login(self, login: str) -> StaffUser | None:
        return await self._session.scalar(select(StaffUser).where(StaffUser.login == login))

    async def get_staff_by_email(self, email: str) -> StaffUser | None:
        return await self._session.scalar(select(StaffUser).where(StaffUser.email == email))

    async def get_expert_profile(self, staff_id: UUID) -> ExpertProfile | None:
        return await self._session.get(ExpertProfile, staff_id)

    async def list_membership_group_ids(self, expert_id: UUID) -> list[UUID]:
        return list(
            await self._session.scalars(
                select(ExpertGroupMembership.specialist_group_id).where(
                    ExpertGroupMembership.expert_id == expert_id
                )
            )
        )

    async def active_workload(self, expert_id: UUID) -> int:
        value = await self._session.scalar(
            select(func.count(func.distinct(Appeal.id)))
            .join(AppealParticipant, AppealParticipant.appeal_id == Appeal.id)
            .where(
                AppealParticipant.staff_user_id == expert_id,
                AppealParticipant.is_active.is_(True),
                Appeal.status.in_(ACTIVE_WORKLOAD_STATUSES),
            )
        )
        return int(value or 0)

    async def expert_is_eligible(self, expert_id: UUID, category_id: UUID) -> bool:
        value = await self._session.scalar(
            select(func.count(CategoryGroupRule.id))
            .join(
                ExpertGroupMembership,
                ExpertGroupMembership.specialist_group_id
                == CategoryGroupRule.specialist_group_id,
            )
            .join(
                SpecialistGroup,
                SpecialistGroup.id == CategoryGroupRule.specialist_group_id,
            )
            .where(
                CategoryGroupRule.category_id == category_id,
                ExpertGroupMembership.expert_id == expert_id,
                SpecialistGroup.is_active.is_(True),
            )
        )
        return bool(value)

    async def add(self, record: object) -> None:
        self._session.add(record)
        await self._session.flush()

    async def add_all(self, records: list[object]) -> None:
        self._session.add_all(records)
        await self._session.flush()

    async def revoke_sessions(self, staff_id: UUID, now: datetime) -> None:
        await self._session.execute(
            update(StaffSession)
            .where(StaffSession.staff_user_id == staff_id, StaffSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )

    async def consume_open_invitations(self, staff_id: UUID, now: datetime) -> None:
        await self._session.execute(
            update(StaffInvitation)
            .where(
                StaffInvitation.staff_user_id == staff_id,
                StaffInvitation.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )

    async def invitation_for_update(self, digest: bytes) -> StaffInvitation | None:
        return await self._session.scalar(
            select(StaffInvitation).where(StaffInvitation.token_digest == digest).with_for_update()
        )

    async def list_applicant_types(self, *, active_only: bool = False) -> list[ApplicantTypeConfig]:
        statement = select(ApplicantTypeConfig)
        if active_only:
            statement = statement.where(ApplicantTypeConfig.is_active.is_(True))
        return list(
            await self._session.scalars(
                statement.order_by(ApplicantTypeConfig.sort_order, ApplicantTypeConfig.label)
            )
        )

    async def get_applicant_type(self, item_id: UUID) -> ApplicantTypeConfig | None:
        return await self._session.get(ApplicantTypeConfig, item_id)

    async def get_applicant_type_by_code(self, code: str) -> ApplicantTypeConfig | None:
        return await self._session.scalar(
            select(ApplicantTypeConfig).where(ApplicantTypeConfig.code == code)
        )

    async def list_categories(self, *, active_only: bool = False) -> list[Category]:
        statement = select(Category)
        if active_only:
            statement = statement.where(Category.is_active.is_(True))
        return list(
            await self._session.scalars(statement.order_by(Category.sort_order, Category.name))
        )

    async def get_category(self, item_id: UUID) -> Category | None:
        return await self._session.get(Category, item_id)

    async def category_by_slug(self, slug: str) -> Category | None:
        return await self._session.scalar(select(Category).where(Category.slug == slug))

    async def list_questions(self, *, active_only: bool = False) -> list[IntakeQuestion]:
        statement = select(IntakeQuestion)
        if active_only:
            statement = statement.where(IntakeQuestion.is_active.is_(True))
        return list(
            await self._session.scalars(
                statement.order_by(IntakeQuestion.sort_order, IntakeQuestion.label)
            )
        )

    async def get_question(self, item_id: UUID) -> IntakeQuestion | None:
        return await self._session.get(IntakeQuestion, item_id)

    async def question_by_code(self, code: str) -> IntakeQuestion | None:
        return await self._session.scalar(select(IntakeQuestion).where(IntakeQuestion.code == code))

    async def question_mappings(self) -> list[CategoryIntakeQuestion]:
        return list(
            await self._session.scalars(
                select(CategoryIntakeQuestion).order_by(
                    CategoryIntakeQuestion.category_id,
                    CategoryIntakeQuestion.sort_order,
                )
            )
        )

    async def replace_category_questions(
        self, category_id: UUID, mappings: list[CategoryIntakeQuestion]
    ) -> None:
        await self._session.execute(
            delete(CategoryIntakeQuestion).where(CategoryIntakeQuestion.category_id == category_id)
        )
        self._session.add_all(mappings)
        await self._session.flush()

    async def list_groups(self) -> list[SpecialistGroup]:
        return list(
            await self._session.scalars(select(SpecialistGroup).order_by(SpecialistGroup.name))
        )

    async def get_group(self, item_id: UUID) -> SpecialistGroup | None:
        return await self._session.get(SpecialistGroup, item_id)

    async def group_by_slug(self, slug: str) -> SpecialistGroup | None:
        return await self._session.scalar(
            select(SpecialistGroup).where(SpecialistGroup.slug == slug)
        )

    async def group_member_ids(self, group_id: UUID) -> list[UUID]:
        return list(
            await self._session.scalars(
                select(ExpertGroupMembership.expert_id).where(
                    ExpertGroupMembership.specialist_group_id == group_id
                )
            )
        )

    async def replace_group_members(
        self, group_id: UUID, memberships: list[ExpertGroupMembership]
    ) -> None:
        await self._session.execute(
            delete(ExpertGroupMembership).where(
                ExpertGroupMembership.specialist_group_id == group_id
            )
        )
        self._session.add_all(memberships)
        await self._session.flush()

    async def routing_group_ids(self, category_id: UUID) -> list[UUID]:
        return list(
            await self._session.scalars(
                select(CategoryGroupRule.specialist_group_id).where(
                    CategoryGroupRule.category_id == category_id
                )
            )
        )

    async def replace_routing(self, category_id: UUID, rules: list[CategoryGroupRule]) -> None:
        await self._session.execute(
            delete(CategoryGroupRule).where(CategoryGroupRule.category_id == category_id)
        )
        self._session.add_all(rules)
        await self._session.flush()

    async def list_crisis_rules(self, *, active_only: bool = False) -> list[CrisisRule]:
        statement = select(CrisisRule)
        if active_only:
            statement = statement.where(CrisisRule.is_active.is_(True))
        return list(
            await self._session.scalars(statement.order_by(CrisisRule.sort_order, CrisisRule.id))
        )

    async def get_crisis_rule(self, item_id: UUID) -> CrisisRule | None:
        return await self._session.get(CrisisRule, item_id)

    async def crisis_rule_by_normalized(self, normalized: str) -> CrisisRule | None:
        return await self._session.scalar(
            select(CrisisRule).where(CrisisRule.normalized_phrase == normalized)
        )

    async def list_support_resources(
        self, *, active_only: bool = False
    ) -> list[CrisisSupportResource]:
        statement = select(CrisisSupportResource)
        if active_only:
            statement = statement.where(CrisisSupportResource.is_active.is_(True))
        return list(
            await self._session.scalars(
                statement.order_by(CrisisSupportResource.sort_order, CrisisSupportResource.title)
            )
        )

    async def get_support_resource(self, item_id: UUID) -> CrisisSupportResource | None:
        return await self._session.get(CrisisSupportResource, item_id)

    async def add_audit(self, audit: AuditLog) -> None:
        self._session.add(audit)
        await self._session.flush()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def list_appeal_metadata(
        self, *, page: int, page_size: int, status: AppealStatus | None = None
    ) -> tuple[list[object], int]:
        filters = [Appeal.status == status] if status is not None else []
        total = int(
            await self._session.scalar(select(func.count(Appeal.id)).where(*filters)) or 0
        )
        statement = (
            select(Appeal, Category, StaffUser)
            .outerjoin(Category, Category.id == Appeal.category_id)
            .outerjoin(StaffUser, StaffUser.id == Appeal.assigned_expert_id)
            .where(*filters)
            .order_by(Appeal.updated_at.desc(), Appeal.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list((await self._session.execute(statement)).all()), total

    async def get_appeal_for_update(self, appeal_id: UUID) -> Appeal | None:
        return await self._session.scalar(
            select(Appeal).where(Appeal.id == appeal_id).with_for_update()
        )

    async def get_appeal_metadata(self, appeal_id: UUID) -> object | None:
        return (
            await self._session.execute(
                select(Appeal, Category, StaffUser)
                .outerjoin(Category, Category.id == Appeal.category_id)
                .outerjoin(StaffUser, StaffUser.id == Appeal.assigned_expert_id)
                .where(Appeal.id == appeal_id)
            )
        ).one_or_none()

    async def active_primary_participant(self, appeal_id: UUID) -> AppealParticipant | None:
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

    async def flush(self) -> None:
        await self._session.flush()

    async def list_audit(
        self,
        *,
        page: int,
        page_size: int,
        action: str | None,
        actor_id: UUID | None,
        entity_type: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> tuple[list[object], int]:
        filters = []
        if action:
            filters.append(AuditLog.action == action)
        if actor_id:
            filters.append(AuditLog.actor_staff_user_id == actor_id)
        if entity_type:
            filters.append(AuditLog.entity_type == entity_type)
        if date_from:
            filters.append(AuditLog.created_at >= date_from)
        if date_to:
            filters.append(AuditLog.created_at < date_to)
        total = int(
            await self._session.scalar(select(func.count(AuditLog.id)).where(*filters)) or 0
        )
        statement = (
            select(AuditLog, StaffUser.display_name)
            .outerjoin(StaffUser, StaffUser.id == AuditLog.actor_staff_user_id)
            .where(*filters)
            .order_by(AuditLog.created_at.desc(), AuditLog.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list((await self._session.execute(statement)).all()), total

    async def analytics_summary(self, start: datetime, end: datetime) -> dict[str, object]:
        in_range = and_(Appeal.created_at >= start, Appeal.created_at < end)
        active_statuses = tuple(value.value for value in ACTIVE_WORKLOAD_STATUSES)
        summary = (
            await self._session.execute(
                select(
                    func.count(Appeal.id),
                    func.count(Appeal.id).filter(Appeal.status == AppealStatus.NEW),
                    func.count(Appeal.id).filter(Appeal.status.in_(active_statuses)),
                    func.count(Appeal.id).filter(Appeal.status == AppealStatus.COMPLETED),
                    func.count(Appeal.id).filter(Appeal.priority == "urgent"),
                    func.count(Appeal.id).filter(Appeal.return_count > 0),
                    func.avg(
                        extract("epoch", Appeal.operator_accepted_at - Appeal.created_at)
                    ).filter(Appeal.operator_accepted_at.is_not(None)),
                    func.avg(
                        extract("epoch", Appeal.first_specialist_response_at - Appeal.created_at)
                    ).filter(Appeal.first_specialist_response_at.is_not(None)),
                    func.avg(extract("epoch", Appeal.completed_at - Appeal.created_at)).filter(
                        Appeal.completed_at.is_not(None)
                    ),
                ).where(in_range)
            )
        ).one()
        keys = (
            "total",
            "new",
            "active",
            "completed",
            "urgent",
            "returned",
            "avg_operator",
            "avg_response",
            "avg_resolution",
        )
        return dict(zip(keys, summary, strict=True))

    async def analytics_distribution(
        self, dimension: str, start: datetime, end: datetime
    ) -> list[tuple[str, int]]:
        if dimension == "category":
            key = func.coalesce(Category.name, "Без категории")
            statement = select(key, func.count(Appeal.id)).outerjoin(
                Category, Category.id == Appeal.category_id
            )
        elif dimension == "applicant_type":
            key = Appeal.applicant_type
            statement = select(key, func.count(Appeal.id))
        else:
            key = Appeal.status
            statement = select(key, func.count(Appeal.id))
        statement = (
            statement.where(Appeal.created_at >= start, Appeal.created_at < end)
            .group_by(key)
            .order_by(func.count(Appeal.id).desc(), key)
        )
        rows = await self._session.execute(statement)
        return [
            (str(getattr(key_value, "value", key_value)), int(count))
            for key_value, count in rows
        ]

    async def analytics_daily(self, start: datetime, end: datetime) -> list[tuple[object, int]]:
        day = cast(Appeal.created_at, Date)
        statement = (
            select(day, func.count(Appeal.id))
            .where(Appeal.created_at >= start, Appeal.created_at < end)
            .group_by(day)
            .order_by(day)
        )
        return [(value, int(count)) for value, count in await self._session.execute(statement)]

    async def analytics_workloads(self, start: datetime, end: datetime) -> list[object]:
        active_count = func.count(func.distinct(AppealParticipant.appeal_id)).filter(
            AppealParticipant.is_active.is_(True),
            Appeal.status.in_(ACTIVE_WORKLOAD_STATUSES),
        )
        expert_rows = await self._session.execute(
            select(
                StaffUser.id,
                StaffUser.display_name,
                StaffUser.role,
                active_count,
                ExpertProfile.max_active_appeals,
            )
            .join(ExpertProfile, ExpertProfile.staff_user_id == StaffUser.id)
            .outerjoin(AppealParticipant, AppealParticipant.staff_user_id == StaffUser.id)
            .outerjoin(Appeal, Appeal.id == AppealParticipant.appeal_id)
            .where(StaffUser.role == StaffRole.EXPERT, StaffUser.is_active.is_(True))
            .group_by(StaffUser.id, ExpertProfile.max_active_appeals)
            .order_by(StaffUser.display_name)
        )
        operator_actions = func.count(AuditLog.id).filter(
            AuditLog.created_at >= start,
            AuditLog.created_at < end,
            AuditLog.action.like("operator.%"),
        )
        operator_rows = await self._session.execute(
            select(
                StaffUser.id,
                StaffUser.display_name,
                StaffUser.role,
                operator_actions,
            )
            .outerjoin(AuditLog, AuditLog.actor_staff_user_id == StaffUser.id)
            .where(StaffUser.role == StaffRole.OPERATOR, StaffUser.is_active.is_(True))
            .group_by(StaffUser.id)
            .order_by(StaffUser.display_name)
        )
        return [(*row, None) for row in operator_rows] + list(expert_rows)

    async def export_appeal_metadata(self, start: datetime, end: datetime) -> list[object]:
        statement = (
            select(
                Appeal.id,
                Appeal.created_at,
                Appeal.applicant_type,
                Category.name,
                Appeal.status,
                Appeal.priority,
                Appeal.crisis_flag,
                Appeal.operator_accepted_at,
                Appeal.first_specialist_response_at,
                Appeal.completed_at,
                Appeal.return_count,
            )
            .outerjoin(Category, Category.id == Appeal.category_id)
            .where(Appeal.created_at >= start, Appeal.created_at < end)
            .order_by(Appeal.created_at, Appeal.id)
        )
        return list((await self._session.execute(statement)).all())
