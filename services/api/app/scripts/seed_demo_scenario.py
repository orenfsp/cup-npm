import argparse
import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select

from app.core.config import AppEnvironment, Settings, get_settings
from app.core.crypto import track_lookup_digest
from app.db import create_database
from app.db.models import (
    Appeal,
    AppealParticipant,
    AssignmentHistory,
    AuditLog,
    Category,
    StaffUser,
    StatusHistory,
)
from app.db.models.enums import (
    AppealParticipantRole,
    AppealPriority,
    AppealStatus,
)


@dataclass(frozen=True, slots=True)
class DemoAppealDefinition:
    key: str
    days_ago: int
    applicant_type: str
    category_slug: str
    status: AppealStatus
    priority: AppealPriority
    crisis_flag: bool = False
    return_count: int = 0
    assigned: bool = False


DEMO_APPEALS = (
    DemoAppealDefinition(
        "new-bullying", 0, "student", "bullying-insults", AppealStatus.NEW, AppealPriority.STANDARD
    ),
    DemoAppealDefinition(
        "crisis-new",
        1,
        "student",
        "pressure-threats",
        AppealStatus.NEW,
        AppealPriority.STANDARD,
        True,
    ),
    DemoAppealDefinition(
        "urgent-assigned",
        2,
        "parent",
        "cyberbullying",
        AppealStatus.ASSIGNED,
        AppealPriority.URGENT,
        assigned=True,
    ),
    DemoAppealDefinition(
        "in-progress",
        4,
        "teacher",
        "classmate-conflict",
        AppealStatus.IN_PROGRESS,
        AppealPriority.STANDARD,
        assigned=True,
    ),
    DemoAppealDefinition(
        "clarification",
        7,
        "student",
        "teacher-conflict",
        AppealStatus.NEEDS_CLARIFICATION,
        AppealPriority.STANDARD,
        assigned=True,
    ),
    DemoAppealDefinition(
        "answer-ready",
        10,
        "parent",
        "legal-question",
        AppealStatus.ANSWER_READY,
        AppealPriority.STANDARD,
        assigned=True,
    ),
    DemoAppealDefinition(
        "completed",
        14,
        "student",
        "parent-conflict",
        AppealStatus.COMPLETED,
        AppealPriority.LOW,
        assigned=True,
    ),
    DemoAppealDefinition(
        "returned",
        20,
        "teacher",
        "unsure",
        AppealStatus.RETURNED,
        AppealPriority.STANDARD,
        return_count=1,
    ),
)


def _id(kind: str, key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"https://otklik.local/demo/{kind}/{key}")


async def seed_demo_scenario(settings: Settings, *, allow_production: bool = False) -> int:
    """Create deterministic metadata-only demo appeals without sensitive fake content."""

    if settings.app_env is AppEnvironment.PRODUCTION and not allow_production:
        raise RuntimeError("Demo scenario seeding is disabled in production.")
    track_secret = settings.track_hmac_secret
    if track_secret is None or not track_secret.get_secret_value():
        raise RuntimeError("TRACK_HMAC_SECRET is required for the demo scenario.")
    database = create_database(settings.database_url)
    created = 0
    try:
        async with database.session_factory() as session:
            categories = {item.slug: item for item in await session.scalars(select(Category))}
            expert = await session.scalar(
                select(StaffUser).where(StaffUser.login == settings.demo_expert_login)
            )
            operator = await session.scalar(
                select(StaffUser).where(StaffUser.login == settings.demo_operator_login)
            )
            if expert is None or operator is None:
                raise RuntimeError("Run seed_demo_staff before seed_demo_scenario.")
            now = datetime.now(UTC)
            for definition in DEMO_APPEALS:
                appeal_id = _id("appeal", definition.key)
                if await session.get(Appeal, appeal_id) is not None:
                    continue
                category = categories.get(definition.category_slug)
                if category is None:
                    raise RuntimeError(f"Missing demo category: {definition.category_slug}")
                created_at = now - timedelta(days=definition.days_ago, hours=2)
                accepted_at = created_at + timedelta(hours=1) if definition.assigned else None
                response_at = (
                    created_at + timedelta(hours=3)
                    if definition.status
                    in {
                        AppealStatus.IN_PROGRESS,
                        AppealStatus.NEEDS_CLARIFICATION,
                        AppealStatus.ANSWER_READY,
                        AppealStatus.COMPLETED,
                    }
                    else None
                )
                answer_ready_at = (
                    created_at + timedelta(hours=8)
                    if definition.status in {AppealStatus.ANSWER_READY, AppealStatus.COMPLETED}
                    else None
                )
                completed_at = (
                    created_at + timedelta(hours=12)
                    if definition.status is AppealStatus.COMPLETED
                    else None
                )
                appeal = Appeal(
                    id=appeal_id,
                    track_digest=track_lookup_digest(
                        track_secret.get_secret_value(), f"DEMO-METADATA-{definition.key}"
                    ),
                    applicant_type=definition.applicant_type,
                    category_id=category.id,
                    status=definition.status,
                    priority=definition.priority,
                    crisis_flag=definition.crisis_flag,
                    assigned_expert_id=expert.id if definition.assigned else None,
                    operator_accepted_at=accepted_at,
                    first_specialist_response_at=response_at,
                    answer_ready_at=answer_ready_at,
                    completed_at=completed_at,
                    return_count=definition.return_count,
                    created_at=created_at,
                    updated_at=completed_at
                    or answer_ready_at
                    or response_at
                    or accepted_at
                    or created_at,
                )
                session.add(appeal)
                session.add(
                    StatusHistory(
                        id=_id("status", definition.key),
                        appeal_id=appeal_id,
                        from_status=None,
                        to_status=definition.status,
                        changed_by_staff_user_id=operator.id,
                        reason="DEMO-ONLY synthetic workflow state.",
                        created_at=created_at,
                    )
                )
                if definition.assigned:
                    session.add(
                        AppealParticipant(
                            id=_id("participant", definition.key),
                            appeal_id=appeal_id,
                            staff_user_id=expert.id,
                            participant_role=AppealParticipantRole.PRIMARY,
                            is_active=True,
                            joined_at=accepted_at or created_at,
                        )
                    )
                    session.add(
                        AssignmentHistory(
                            id=_id("assignment", definition.key),
                            appeal_id=appeal_id,
                            from_expert_id=None,
                            to_expert_id=expert.id,
                            changed_by_staff_user_id=operator.id,
                            reason="DEMO-ONLY synthetic assignment.",
                            created_at=accepted_at or created_at,
                        )
                    )
                    session.add(
                        AuditLog(
                            id=_id("audit", definition.key),
                            actor_staff_user_id=operator.id,
                            action="operator.demo_triage",
                            entity_type="appeal",
                            entity_id=appeal_id,
                            reason="DEMO-ONLY synthetic activity.",
                            metadata_json={"demo": True},
                            created_at=accepted_at or created_at,
                        )
                    )
                created += 1
            await session.commit()
    finally:
        await database.close()
    print(f"Demo scenario seed complete: {created} metadata-only appeals created.")
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Create idempotent demo analytics metadata.")
    parser.add_argument("--allow-production", action="store_true")
    args = parser.parse_args()
    asyncio.run(seed_demo_scenario(get_settings(), allow_production=args.allow_production))


if __name__ == "__main__":
    main()
