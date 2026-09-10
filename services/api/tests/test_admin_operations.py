from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest

from app.core.email import SMTPMailer
from app.core.errors import ValidationError
from app.db.models import (
    Appeal,
    AppealContent,
    AppealMessage,
    AppealParticipant,
    ApplicantTypeConfig,
    AssignmentHistory,
    AuditLog,
    Category,
    CategoryGroupRule,
    CategoryIntakeQuestion,
    CrisisContact,
    ExpertProfile,
    IntakeQuestion,
    InternalNote,
    SpecialistGroup,
    StaffUser,
    StatusHistory,
)
from app.db.models.enums import (
    AppealParticipantRole,
    AppealPriority,
    AppealStatus,
    MessageAuthorType,
    StaffRole,
)
from app.db.repositories.admin import AdminRepository
from app.db.repositories.operator import OperatorRepository, RoutingCandidateRecord
from app.modules.admin.schemas import (
    AdminAppealInterventionRequest,
    AdminAppealItem,
    AnalyticsResponse,
    RoutingUpdateRequest,
    StaffCreateRequest,
)
from app.modules.admin.service import AdminService
from app.modules.routing.service import RoutingService
from app.scripts.seed_demo_scenario import DEMO_APPEALS, _id
from app.scripts.seed_reference_data import seed_applicant_types, seed_intake_questions


class NoMail:
    async def send_staff_setup(self, **kwargs) -> None:
        del kwargs


class AnalyticsRepository:
    def __init__(self, appeal: Appeal, category: Category) -> None:
        self.appeal = appeal
        self.category = category
        self.calls: list[str] = []
        self.sensitive_tables: list[object] = []

    async def analytics_summary(self, start, end):
        self.calls.append("summary")
        assert start.date() == date(2026, 9, 1)
        assert end.date() == date(2026, 10, 1)
        return {
            "total": 4,
            "new": 1,
            "active": 2,
            "completed": 1,
            "urgent": 1,
            "returned": 1,
            "avg_operator": Decimal("3600"),
            "avg_response": Decimal("7200"),
            "avg_resolution": Decimal("14400"),
        }

    async def analytics_distribution(self, dimension, start, end):
        del start, end
        self.calls.append(dimension)
        return [("value", 4)]

    async def analytics_daily(self, start, end):
        del start, end
        self.calls.append("daily")
        return [(date(2026, 9, 2), 4)]

    async def analytics_workloads(self, start, end):
        del start, end
        self.calls.append("workloads")
        return [(uuid4(), "Эксперт", StaffRole.EXPERT, 2, 8)]

    async def export_appeal_metadata(self, start, end):
        del start, end
        self.calls.append("export")
        return [
            (
                self.appeal.id,
                self.appeal.created_at,
                self.appeal.applicant_type,
                self.category.name,
                self.appeal.status,
                self.appeal.priority,
                self.appeal.crisis_flag,
                self.appeal.operator_accepted_at,
                self.appeal.first_specialist_response_at,
                self.appeal.completed_at,
                self.appeal.return_count,
            )
        ]


def _service(repository, test_settings) -> AdminService:
    return AdminService(
        cast(AdminRepository, repository),
        test_settings,
        cast(SMTPMailer, NoMail()),
    )


def test_staff_create_schema_enforces_role_specific_expert_fields() -> None:
    operator = StaffCreateRequest(
        login="operator", email="operator@example.org", display_name="Оператор", role="operator"
    )
    admin = StaffCreateRequest(
        login="admin", email="admin@example.org", display_name="Администратор", role="admin"
    )
    expert = StaffCreateRequest(
        login="expert",
        email="expert@example.org",
        display_name="Эксперт",
        role="expert",
        public_specialist_label="Психолог",
        max_active_appeals=8,
    )
    assert operator.public_specialist_label is None
    assert admin.public_specialist_label is None
    assert expert.max_active_appeals == 8
    with pytest.raises(ValueError):
        StaffCreateRequest(
            login="bad",
            email="bad@example.org",
            display_name="Без специализации",
            role="expert",
        )
    with pytest.raises(ValueError):
        StaffCreateRequest(
            login="bad-operator",
            email="bad-operator@example.org",
            display_name="Оператор",
            role="operator",
            public_specialist_label="Не должно примениться",
        )


async def test_metadata_analytics_computes_real_shares_and_empty_safe_metrics(
    test_settings,
) -> None:
    created = datetime(2026, 9, 2, tzinfo=UTC)
    category = Category(id=uuid4(), slug="configured", name="Настроенная")
    appeal = Appeal(
        id=uuid4(),
        track_digest=b"d" * 32,
        applicant_type="student",
        category_id=category.id,
        status=AppealStatus.COMPLETED,
        priority=AppealPriority.URGENT,
        crisis_flag=False,
        return_count=1,
        created_at=created,
        updated_at=created,
        completed_at=created + timedelta(hours=4),
    )
    repository = AnalyticsRepository(appeal, category)
    result = await _service(repository, test_settings).analytics(
        date(2026, 9, 1), date(2026, 9, 30)
    )
    assert result.total == 4
    assert result.urgent_share == 0.25
    assert result.returned_share == 0.25
    assert result.avg_operator_acceptance_seconds == 3600
    assert result.workloads[0].capacity == 8
    with pytest.raises(ValidationError):
        await _service(repository, test_settings).analytics(date(2026, 10, 1), date(2026, 9, 1))


async def test_csv_export_never_queries_or_emits_sensitive_tables(test_settings) -> None:
    unique_secrets = [
        "APPEAL-BODY-UNIQUE",
        "CHAT-UNIQUE",
        "NOTE-UNIQUE",
        "CRISIS-CONTACT-UNIQUE",
    ]
    now = datetime(2026, 9, 5, tzinfo=UTC)
    category = Category(id=uuid4(), slug="safe", name="Safe category")
    appeal = Appeal(
        id=uuid4(),
        track_digest=b"h" * 32,
        applicant_type="teacher",
        category_id=category.id,
        status=AppealStatus.COMPLETED,
        priority=AppealPriority.STANDARD,
        crisis_flag=True,
        return_count=1,
        created_at=now,
        updated_at=now,
        completed_at=now + timedelta(hours=2),
    )
    repository = AnalyticsRepository(appeal, category)
    repository.sensitive_tables = [
        AppealContent(
            appeal_id=appeal.id, encrypted_content=unique_secrets[0].encode(), key_version=1
        ),
        AppealMessage(
            id=uuid4(),
            appeal_id=appeal.id,
            author_type=MessageAuthorType.APPLICANT,
            encrypted_body=unique_secrets[1].encode(),
            key_version=1,
        ),
        InternalNote(
            id=uuid4(),
            appeal_id=appeal.id,
            author_staff_user_id=uuid4(),
            encrypted_body=unique_secrets[2].encode(),
            key_version=1,
        ),
        CrisisContact(
            appeal_id=appeal.id,
            encrypted_contact=unique_secrets[3].encode(),
            key_version=1,
        ),
    ]
    body = await _service(repository, test_settings).analytics_csv(
        date(2026, 9, 1), date(2026, 9, 30)
    )
    assert body.startswith(b"\xef\xbb\xbf")
    assert str(appeal.id).encode() in body
    assert b"track_digest" not in body
    assert repository.calls == ["export"]
    for secret in unique_secrets:
        assert secret.encode() not in body


class InterventionRepository:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.category = Category(id=uuid4(), slug="configured", name="Категория")
        self.old = StaffUser(
            id=uuid4(),
            login="old",
            password_hash="hash",
            role=StaffRole.EXPERT,
            is_active=True,
            display_name="Старый",
            created_at=now,
            updated_at=now,
        )
        self.new = StaffUser(
            id=uuid4(),
            login="new",
            password_hash="hash",
            role=StaffRole.EXPERT,
            is_active=True,
            display_name="Новый",
            created_at=now,
            updated_at=now,
        )
        self.profiles = {
            self.old.id: ExpertProfile(staff_user_id=self.old.id, max_active_appeals=5),
            self.new.id: ExpertProfile(staff_user_id=self.new.id, max_active_appeals=5),
        }
        self.appeal = Appeal(
            id=uuid4(),
            track_digest=b"i" * 32,
            applicant_type="student",
            category_id=self.category.id,
            status=AppealStatus.IN_PROGRESS,
            priority=AppealPriority.STANDARD,
            assigned_expert_id=self.old.id,
            crisis_flag=False,
            return_count=0,
            created_at=now,
            updated_at=now,
        )
        self.primary = AppealParticipant(
            id=uuid4(),
            appeal_id=self.appeal.id,
            staff_user_id=self.old.id,
            participant_role=AppealParticipantRole.PRIMARY,
            is_active=True,
            joined_at=now,
        )
        self.added: list[object] = []
        self.commits = 0

    async def get_appeal_for_update(self, appeal_id):
        return self.appeal if appeal_id == self.appeal.id else None

    async def get_staff(self, staff_id):
        return (
            self.old if staff_id == self.old.id else self.new if staff_id == self.new.id else None
        )

    async def get_expert_profile(self, staff_id):
        return self.profiles.get(staff_id)

    async def expert_is_eligible(self, expert_id, category_id):
        return expert_id == self.new.id and category_id == self.category.id

    async def active_workload(self, expert_id):
        del expert_id
        return 1

    async def active_primary_participant(self, appeal_id):
        return self.primary if appeal_id == self.appeal.id and self.primary.is_active else None

    async def active_participant(self, appeal_id, staff_user_id):
        del appeal_id, staff_user_id
        return None

    async def flush(self):
        return None

    async def add_all(self, records):
        self.added.extend(records)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None

    async def get_appeal_metadata(self, appeal_id):
        if appeal_id != self.appeal.id:
            return None
        assigned = self.new if self.appeal.assigned_expert_id == self.new.id else self.old
        return self.appeal, self.category, assigned


async def test_admin_stuck_appeal_intervention_is_atomic_and_audited(test_settings) -> None:
    repository = InterventionRepository()
    admin_id = uuid4()
    result = await _service(repository, test_settings).intervene_appeal(
        repository.appeal.id,
        AdminAppealInterventionRequest(
            status="assigned",
            priority="urgent",
            assigned_expert_id=repository.new.id,
            reason="Восстановление зависшего назначения",
        ),
        admin_id=admin_id,
    )
    assert result.status is AppealStatus.ASSIGNED
    assert result.priority is AppealPriority.URGENT
    assert result.assigned_expert_id == repository.new.id
    assert repository.primary.is_active is False
    assert repository.commits == 1
    assert any(
        isinstance(item, AppealParticipant) and item.staff_user_id == repository.new.id
        for item in repository.added
    )
    assert any(isinstance(item, AssignmentHistory) for item in repository.added)
    assert any(isinstance(item, StatusHistory) for item in repository.added)
    audit = next(item for item in repository.added if isinstance(item, AuditLog))
    assert audit.reason == "Восстановление зависшего назначения"
    assert audit.metadata_json == {"fields": ["assigned_expert_id", "status", "priority"]}


async def test_failed_admin_intervention_keeps_assignment_unchanged(test_settings) -> None:
    repository = InterventionRepository()
    inactive_id = repository.new.id
    repository.new.is_active = False
    with pytest.raises(ValidationError):
        await _service(repository, test_settings).intervene_appeal(
            repository.appeal.id,
            AdminAppealInterventionRequest(
                assigned_expert_id=inactive_id,
                status="assigned",
                reason="Попытка безопасной перенастройки",
            ),
            admin_id=uuid4(),
        )
    assert repository.appeal.assigned_expert_id == repository.old.id
    assert repository.primary.is_active is True
    assert repository.commits == 0


def test_demo_scenario_identifiers_are_deterministic_and_unique() -> None:
    first = [_id("appeal", item.key) for item in DEMO_APPEALS]
    second = [_id("appeal", item.key) for item in DEMO_APPEALS]
    assert first == second
    assert len(first) == len(set(first))


class ReferenceSeedRepository:
    def __init__(self) -> None:
        self.types: list[ApplicantTypeConfig] = []
        self.questions: list[IntakeQuestion] = []
        self.mappings: list[CategoryIntakeQuestion] = []
        self.category = Category(id=uuid4(), slug="seed-category", name="Seed", is_active=True)

    async def get_applicant_type_by_code(self, code):
        return next((item for item in self.types if item.code == code), None)

    async def question_by_code(self, code):
        return next((item for item in self.questions if item.code == code), None)

    async def question_mappings(self):
        return list(self.mappings)

    async def list_categories(self, *, active_only=False):
        del active_only
        return [self.category]

    async def add(self, item):
        if isinstance(item, ApplicantTypeConfig):
            self.types.append(item)
        elif isinstance(item, IntakeQuestion):
            self.questions.append(item)
        elif isinstance(item, CategoryIntakeQuestion):
            self.mappings.append(item)

    async def commit(self):
        return None


async def test_phase6_reference_seed_is_idempotent_and_respects_removed_mappings() -> None:
    repository = ReferenceSeedRepository()
    first_types = await seed_applicant_types(cast(AdminRepository, repository))
    second_types = await seed_applicant_types(cast(AdminRepository, repository))
    first_questions = await seed_intake_questions(cast(AdminRepository, repository))
    mapping_count = len(repository.mappings)
    repository.mappings.pop()
    second_questions = await seed_intake_questions(cast(AdminRepository, repository))

    assert first_types[0] == 3
    assert second_types[0] == 0
    assert first_questions[0] == 4
    assert second_questions[0] == 0
    assert len(repository.mappings) == mapping_count - 1


def test_admin_operational_and_analytics_schemas_exclude_sensitive_content() -> None:
    forbidden = {
        "description",
        "intake_answers",
        "messages",
        "internal_notes",
        "attachments",
        "crisis_contact",
        "return_explanations",
        "feedback_comment",
        "complaint",
        "track_number",
        "track_digest",
        "ciphertext",
    }
    assert forbidden.isdisjoint(AdminAppealItem.model_fields)
    assert forbidden.isdisjoint(AnalyticsResponse.model_fields)


class C7ConfigurationRepository:
    def __init__(self) -> None:
        self.category = Category(id=uuid4(), slug="new-category", name="Новая категория")
        self.group = SpecialistGroup(
            id=uuid4(), slug="new-group", name="Новая группа", is_active=True
        )
        self.rules: list[CategoryGroupRule] = []

    async def get_category(self, category_id):
        return self.category if category_id == self.category.id else None

    async def get_group(self, group_id):
        return self.group if group_id == self.group.id else None

    async def replace_routing(self, category_id, rules):
        assert category_id == self.category.id
        self.rules = rules

    async def add_audit(self, audit):
        assert audit.action == "admin.routing_changed"

    async def commit(self):
        return None


class C7RoutingRepository:
    def __init__(self, configuration: C7ConfigurationRepository) -> None:
        self.configuration = configuration
        self.expert = StaffUser(
            id=uuid4(),
            login="configured-expert",
            password_hash="hash",
            role=StaffRole.EXPERT,
            is_active=True,
            display_name="Настроенный эксперт",
        )
        self.profile = ExpertProfile(staff_user_id=self.expert.id, max_active_appeals=3)

    async def routing_candidates(self, category_id):
        eligible = any(
            rule.category_id == category_id
            and rule.specialist_group_id == self.configuration.group.id
            for rule in self.configuration.rules
        )
        if not eligible:
            return []
        return [
            RoutingCandidateRecord(
                staff=self.expert,
                profile=self.profile,
                group=self.configuration.group,
                current_load=1,
            )
        ]


async def test_c7_admin_routing_mutation_immediately_changes_recommendation(
    test_settings,
) -> None:
    configuration = C7ConfigurationRepository()
    routing_repository = C7RoutingRepository(configuration)
    routing_service = RoutingService(cast(OperatorRepository, routing_repository))
    before = await routing_service.recommend(configuration.category.id)
    assert before.state == "no_eligible_expert"

    await _service(configuration, test_settings).set_routing(
        configuration.category.id,
        RoutingUpdateRequest(group_ids=[configuration.group.id]),
        admin_id=uuid4(),
    )
    after = await routing_service.recommend(configuration.category.id)
    assert after.state == "recommended"
    assert after.recommended_expert is not None
    assert after.recommended_expert.capacity == 3
