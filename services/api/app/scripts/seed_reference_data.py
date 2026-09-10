import asyncio
from uuid import uuid4

from app.core.config import get_settings
from app.db import create_database
from app.db.models import (
    ApplicantTypeConfig,
    Category,
    CategoryIntakeQuestion,
    CrisisRule,
    IntakeQuestion,
)
from app.db.models.enums import ApplicantTone, IntakeFieldType
from app.db.repositories.admin import AdminRepository
from app.db.repositories.crisis_rules import CrisisRuleRepository
from app.db.repositories.public_appeals import PublicAppealRepository
from app.modules.categories.reference_data import (
    APPLICANT_TYPES,
    INTAKE_QUESTIONS,
    STARTER_CATEGORIES,
    CategoryDefinition,
)
from app.modules.crisis.detector import DEFAULT_CRISIS_RULES


async def seed_categories(
    repository: PublicAppealRepository,
    definitions: tuple[CategoryDefinition, ...] = STARTER_CATEGORIES,
) -> tuple[int, int]:
    created = 0
    updated = 0
    for definition in definitions:
        category = await repository.get_category_by_slug(definition.slug)
        if category is None:
            await repository.add_category(
                Category(
                    id=uuid4(),
                    slug=definition.slug,
                    name=definition.name,
                    description=definition.description,
                    sort_order=definition.sort_order,
                    is_active=True,
                )
            )
            created += 1
            continue
        # Existing rows are administrator-managed and are never overwritten/reactivated.
    await repository.commit()
    return created, updated


async def seed_applicant_types(repository: AdminRepository) -> tuple[int, int]:
    created = 0
    for definition in APPLICANT_TYPES:
        if await repository.get_applicant_type_by_code(definition.code) is not None:
            continue
        await repository.add(
            ApplicantTypeConfig(
                id=uuid4(),
                code=definition.code,
                label=definition.label,
                description=definition.description,
                tone=ApplicantTone(definition.tone),
                is_active=True,
                sort_order=definition.sort_order,
            )
        )
        created += 1
    await repository.commit()
    return created, 0


async def seed_intake_questions(repository: AdminRepository) -> tuple[int, int]:
    created = 0
    newly_created_ids = set()
    questions: dict[str, IntakeQuestion] = {}
    for sort_order, definition in enumerate(INTAKE_QUESTIONS, start=1):
        question = await repository.question_by_code(definition.id)
        if question is None:
            question = IntakeQuestion(
                id=uuid4(),
                code=definition.id,
                label=definition.prompt_formal,
                help_text=None,
                field_type=IntakeFieldType.SHORT_TEXT,
                options_json=[],
                required=False,
                is_active=True,
                sort_order=sort_order * 10,
            )
            await repository.add(question)
            newly_created_ids.add(question.id)
            created += 1
        questions[definition.id] = question
    existing = {
        (item.category_id, item.question_id) for item in await repository.question_mappings()
    }
    for category in await repository.list_categories(active_only=True):
        for sort_order, definition in enumerate(INTAKE_QUESTIONS, start=1):
            question = questions[definition.id]
            if question.id not in newly_created_ids:
                continue
            if (category.id, question.id) in existing:
                continue
            await repository.add(
                CategoryIntakeQuestion(
                    id=uuid4(),
                    category_id=category.id,
                    question_id=question.id,
                    required_override=None,
                    sort_order=sort_order * 10,
                )
            )
    await repository.commit()
    return created, 0


async def seed_crisis_rules(repository: CrisisRuleRepository) -> tuple[int, int]:
    created = 0
    updated = 0
    for sort_order, definition in enumerate(DEFAULT_CRISIS_RULES, start=1):
        rule = await repository.get_by_normalized_phrase(definition.normalized_phrase)
        if rule is None:
            await repository.add(
                CrisisRule(
                    id=uuid4(),
                    phrase=definition.normalized_phrase,
                    normalized_phrase=definition.normalized_phrase,
                    compact_phrase=definition.compact_phrase,
                    is_active=True,
                    allow_compact_match=definition.allow_compact_match,
                    sort_order=sort_order * 10,
                )
            )
            created += 1
            continue
        # Existing rows are administrator-managed metadata. Re-running the seed must not
        # reactivate or overwrite a rule that an administrator changed intentionally.
    await repository.commit()
    return created, updated


async def seed_reference_data() -> None:
    settings = get_settings()
    database = create_database(settings.database_url)
    try:
        async with database.session_factory() as session:
            categories = await seed_categories(PublicAppealRepository(session))
            admin_repository = AdminRepository(session)
            applicant_types = await seed_applicant_types(admin_repository)
            questions = await seed_intake_questions(admin_repository)
            crisis_rules = await seed_crisis_rules(CrisisRuleRepository(session))
    finally:
        await database.close()
    print(
        "Reference seed complete: "
        f"categories={categories[0]} created/{categories[1]} updated; "
        f"applicant_types={applicant_types[0]} created; "
        f"questions={questions[0]} created; "
        f"crisis_rules={crisis_rules[0]} created/{crisis_rules[1]} updated."
    )


def main() -> None:
    asyncio.run(seed_reference_data())


if __name__ == "__main__":
    main()
