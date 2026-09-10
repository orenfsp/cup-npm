import argparse
import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppEnvironment, Settings, get_settings
from app.db import create_database
from app.db.models import (
    Category,
    CategoryGroupRule,
    ExpertGroupMembership,
    ExpertProfile,
    SpecialistGroup,
    StaffUser,
)
from app.db.models.enums import StaffRole
from app.db.repositories.staff_auth import StaffAuthRepository
from app.modules.auth.service import normalize_login
from app.modules.categories.reference_data import STARTER_CATEGORIES
from app.modules.staff.service import StaffManagementService


@dataclass(frozen=True, slots=True)
class DemoStaffDefinition:
    login: str
    password: SecretStr | None
    display_name: str
    role: StaffRole


@dataclass(frozen=True, slots=True)
class DemoRoutingDefinition:
    expert_login: str
    group_slug: str
    group_name: str
    category_slugs: frozenset[str]


def _password_or_fallback(value: SecretStr | None, fallback: SecretStr | None) -> SecretStr | None:
    if value is not None and value.get_secret_value():
        return value
    return fallback


def _definitions(settings: Settings) -> tuple[DemoStaffDefinition, ...]:
    return (
        DemoStaffDefinition(
            settings.demo_operator_login,
            settings.demo_operator_password,
            "Demo Operator",
            StaffRole.OPERATOR,
        ),
        DemoStaffDefinition(
            settings.demo_expert_login,
            settings.demo_expert_password,
            "Demo Expert",
            StaffRole.EXPERT,
        ),
        DemoStaffDefinition(
            settings.demo_psychologist_login,
            _password_or_fallback(
                settings.demo_psychologist_password, settings.demo_expert_password
            ),
            "Психолог",
            StaffRole.EXPERT,
        ),
        DemoStaffDefinition(
            settings.demo_lawyer_login,
            _password_or_fallback(settings.demo_lawyer_password, settings.demo_expert_password),
            "Юрист",
            StaffRole.EXPERT,
        ),
        DemoStaffDefinition(
            settings.demo_social_login,
            _password_or_fallback(settings.demo_social_password, settings.demo_expert_password),
            "Социальный педагог",
            StaffRole.EXPERT,
        ),
        DemoStaffDefinition(
            settings.demo_conflict_login,
            _password_or_fallback(settings.demo_conflict_password, settings.demo_expert_password),
            "Конфликтолог",
            StaffRole.EXPERT,
        ),
        DemoStaffDefinition(
            settings.demo_admin_login,
            settings.demo_admin_password,
            "Demo Administrator",
            StaffRole.ADMIN,
        ),
    )


def _routing_definitions(settings: Settings) -> tuple[DemoRoutingDefinition, ...]:
    all_categories = frozenset(item.slug for item in STARTER_CATEGORIES)
    return (
        DemoRoutingDefinition(
            normalize_login(settings.demo_expert_login),
            "demo_generalists",
            "Демо-специалисты",
            all_categories,
        ),
        DemoRoutingDefinition(
            normalize_login(settings.demo_psychologist_login),
            "psychologists",
            "Психологи",
            frozenset({"bullying-insults", "cyberbullying", "pressure-threats", "parent-conflict"}),
        ),
        DemoRoutingDefinition(
            normalize_login(settings.demo_lawyer_login),
            "lawyers",
            "Юристы",
            frozenset({"pressure-threats", "legal-question"}),
        ),
        DemoRoutingDefinition(
            normalize_login(settings.demo_social_login),
            "social_teachers",
            "Социальные педагоги",
            frozenset(
                {
                    "bullying-insults",
                    "classmate-conflict",
                    "teacher-conflict",
                    "parent-conflict",
                    "unsure",
                }
            ),
        ),
        DemoRoutingDefinition(
            normalize_login(settings.demo_conflict_login),
            "conflict_specialists",
            "Конфликтологи",
            frozenset(
                {
                    "bullying-insults",
                    "classmate-conflict",
                    "teacher-conflict",
                    "parent-conflict",
                }
            ),
        ),
    )


async def seed_demo_staff(settings: Settings, *, allow_production: bool = False) -> None:
    if settings.app_env is AppEnvironment.PRODUCTION and not allow_production:
        raise RuntimeError("Demo staff seeding is disabled in production.")
    definitions = _definitions(settings)
    if any(item.password is None or not item.password.get_secret_value() for item in definitions):
        raise RuntimeError("All DEMO_*_PASSWORD environment variables must be configured.")

    database = create_database(settings.database_url)
    created = 0
    routing_created = 0
    try:
        async with database.session_factory() as session:
            repository = StaffAuthRepository(session)
            created = await _seed_definitions(repository, definitions)
            routing_created = await _seed_demo_routing(
                DemoRoutingSeedRepository(session), _routing_definitions(settings)
            )
    finally:
        await database.close()
    print(
        f"Demo staff seed complete: {created} staff created, "
        f"{len(definitions) - created} existing; {routing_created} routing rows created."
    )


async def _seed_definitions(
    repository: StaffAuthRepository,
    definitions: tuple[DemoStaffDefinition, ...],
) -> int:
    service = StaffManagementService(repository)
    created = 0
    for definition in definitions:
        login = normalize_login(definition.login)
        existing = await repository.get_staff_by_login(login)
        if existing is not None:
            if existing.role is not definition.role:
                raise RuntimeError(f"Existing demo login has a different role: {login}")
            if definition.role is StaffRole.EXPERT:
                profile = await repository.get_expert_profile(existing.id)
                if profile is None:
                    profile = ExpertProfile(staff_user_id=existing.id)
                    await repository.add_expert_profile(profile)
                if profile.public_specialist_label is None:
                    profile.public_specialist_label = definition.display_name
                await repository.commit()
            continue
        password = definition.password
        if password is None or not password.get_secret_value():
            raise RuntimeError("Demo staff passwords must be configured.")
        staff = await service.create_staff_user(
            login=login,
            password=password.get_secret_value(),
            role=definition.role,
            display_name=definition.display_name,
        )
        profile = await repository.get_expert_profile(staff.id)
        if profile is not None and profile.public_specialist_label is None:
            profile.public_specialist_label = definition.display_name
            await repository.commit()
        created += 1
    return created


class DemoRoutingSeedRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def expert(self, login: str) -> StaffUser | None:
        return await self._session.scalar(select(StaffUser).where(StaffUser.login == login))

    async def group(self, slug: str) -> SpecialistGroup | None:
        return await self._session.scalar(
            select(SpecialistGroup).where(SpecialistGroup.slug == slug)
        )

    async def add_group(self, group: SpecialistGroup) -> None:
        self._session.add(group)
        await self._session.flush()

    async def active_categories(self) -> list[Category]:
        return list(
            await self._session.scalars(select(Category).where(Category.is_active.is_(True)))
        )

    async def has_membership(self, expert_id: UUID, group_id: UUID) -> bool:
        return (
            await self._session.scalar(
                select(ExpertGroupMembership.id).where(
                    ExpertGroupMembership.expert_id == expert_id,
                    ExpertGroupMembership.specialist_group_id == group_id,
                )
            )
            is not None
        )

    def add_membership(self, expert_id: UUID, group_id: UUID) -> None:
        self._session.add(
            ExpertGroupMembership(id=uuid4(), expert_id=expert_id, specialist_group_id=group_id)
        )

    async def has_rule(self, category_id: UUID, group_id: UUID) -> bool:
        return (
            await self._session.scalar(
                select(CategoryGroupRule.id).where(
                    CategoryGroupRule.category_id == category_id,
                    CategoryGroupRule.specialist_group_id == group_id,
                )
            )
            is not None
        )

    def add_rule(self, category_id: UUID, group_id: UUID) -> None:
        self._session.add(
            CategoryGroupRule(id=uuid4(), category_id=category_id, specialist_group_id=group_id)
        )

    async def commit(self) -> None:
        await self._session.commit()


async def _seed_demo_routing(
    repository: DemoRoutingSeedRepository,
    definitions: tuple[DemoRoutingDefinition, ...],
) -> int:
    """Create missing demo rows only; never update existing groups or relationships."""

    created = 0
    categories = {item.slug: item for item in await repository.active_categories()}
    for definition in definitions:
        expert = await repository.expert(definition.expert_login)
        if expert is None or expert.role is not StaffRole.EXPERT:
            raise RuntimeError(
                f"Configured demo expert is unavailable for routing seed: {definition.expert_login}"
            )
        group = await repository.group(definition.group_slug)
        if group is None:
            group = SpecialistGroup(
                id=uuid4(),
                slug=definition.group_slug,
                name=definition.group_name,
                description="DEMO-ONLY routing metadata for local workflow testing.",
                is_active=True,
            )
            await repository.add_group(group)
            created += 1
        if not await repository.has_membership(expert.id, group.id):
            repository.add_membership(expert.id, group.id)
            created += 1
        for category_slug in definition.category_slugs:
            category = categories.get(category_slug)
            if category is not None and not await repository.has_rule(category.id, group.id):
                repository.add_rule(category.id, group.id)
                created += 1
    await repository.commit()
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Create idempotent development demo staff.")
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="Explicitly allow demo seeding when APP_ENV=production.",
    )
    args = parser.parse_args()
    asyncio.run(seed_demo_staff(get_settings(), allow_production=args.allow_production))


if __name__ == "__main__":
    main()
