import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.crypto import ContentCrypto
from app.core.errors import ConflictError, ForbiddenError, UnauthorizedError, ValidationError
from app.db.models import (
    Appeal,
    AppealContent,
    AppealIntakeAnswer,
    AppealParticipant,
    AppealReturnExplanation,
    AssignmentHistory,
    Attachment,
    Category,
    CrisisContact,
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
    ApplicantType,
    RejectionKind,
    StaffRole,
    TransferRequestStatus,
)
from app.db.repositories.operator import (
    OperatorDetailRecord,
    OperatorRepository,
    OperatorTransferRecord,
    QueueRecord,
    RoutingCandidateRecord,
)
from app.main import create_app
from app.modules.appeals.crypto_context import (
    appeal_content_aad,
    attachment_aad,
    complaint_body_aad,
    crisis_contact_aad,
    intake_answers_aad,
    rejection_reason_aad,
    return_explanation_aad,
    transfer_reason_aad,
)
from app.modules.appeals.status import applicant_status_text
from app.modules.attachments.storage import PrivateAttachmentStorage
from app.modules.auth.dependencies import get_auth_service
from app.modules.operator.dependencies import get_operator_service
from app.modules.operator.schemas import OperatorTriageRequest
from app.modules.operator.service import OperatorService, operator_queue_sort_key


class FakeOperatorRepository:
    def __init__(self, appeal: Appeal, category: Category | None = None) -> None:
        self.appeal = appeal
        self.categories = {category.id: category} if category else {}
        self.content: AppealContent | None = None
        self.intake: AppealIntakeAnswer | None = None
        self.attachments: list[Attachment] = []
        self.status_history: list[StatusHistory] = []
        self.assignment_history: list[AssignmentHistory] = []
        self.routing: list[RoutingCandidateRecord] = []
        self.staff: dict[UUID, StaffUser] = {}
        self.primary: AppealParticipant | None = None
        self.contact: CrisisContact | None = None
        self.rejection = None
        self.return_explanations: list[AppealReturnExplanation] = []
        self.transfer_records: list[OperatorTransferRecord] = []
        self.complaints: list[StaffComplaint] = []
        self.audits = []
        self.added: list[object] = []
        self.commits = 0
        self.flushed_transfer_states: list[
            tuple[TransferRequestStatus, UUID | None, datetime | None]
        ] = []

    def _record_transfer_flush_states(self) -> None:
        self.flushed_transfer_states.extend(
            (
                record.transfer.status,
                record.transfer.resolved_by_staff_user_id,
                record.transfer.resolved_at,
            )
            for record in self.transfer_records
        )

    async def list_queue(self, **kwargs):
        status = kwargs["status"]
        priority = kwargs["priority"]
        category_id = kwargs["category_id"]
        crisis = kwargs["crisis"]
        assigned = kwargs["assigned"]
        values = [self.appeal]
        if status is not None:
            values = [item for item in values if item.status is status]
        if priority is not None:
            values = [item for item in values if item.priority is priority]
        if category_id is not None:
            values = [item for item in values if item.category_id == category_id]
        if crisis is not None:
            values = [item for item in values if item.crisis_flag is crisis]
        if assigned is not None:
            values = [item for item in values if (item.assigned_expert_id is not None) is assigned]
        return [QueueRecord(item, self.categories.get(item.category_id)) for item in values], len(
            values
        )

    async def queue_counter_rows(self):
        return [self.appeal]

    async def get_detail(self, appeal_id):
        if appeal_id != self.appeal.id:
            return None
        return OperatorDetailRecord(
            self.appeal,
            self.categories.get(self.appeal.category_id),
            None,
            self.content,
            self.intake,
            self.staff.get(self.appeal.assigned_expert_id),
            self.attachments,
            self.status_history,
            self.assignment_history,
            self.return_explanations,
        )

    async def get_appeal_for_update(self, appeal_id):
        return self.appeal if appeal_id == self.appeal.id else None

    async def get_category(self, category_id):
        return self.categories.get(category_id)

    async def list_active_categories(self):
        return list(self.categories.values())

    async def routing_candidates(self, category_id):
        del category_id
        return self.routing

    async def current_primary(self, appeal_id):
        return self.primary if appeal_id == self.appeal.id else None

    async def get_staff(self, staff_id):
        return self.staff.get(staff_id)

    async def list_pending_transfers(self):
        return [
            record
            for record in self.transfer_records
            if record.transfer.status is TransferRequestStatus.PENDING
        ]

    async def get_transfer_for_update(self, transfer_id):
        return next(
            (
                record.transfer
                for record in self.transfer_records
                if record.transfer.id == transfer_id
            ),
            None,
        )

    async def active_participant(self, appeal_id, staff_id):
        if (
            self.primary
            and self.primary.appeal_id == appeal_id
            and self.primary.staff_user_id == staff_id
        ):
            return self.primary
        return None

    async def list_complaints(self, appeal_id):
        return [item for item in self.complaints if item.appeal_id == appeal_id]

    async def flush(self):
        self._record_transfer_flush_states()
        return None

    async def get_attachment(self, appeal_id, attachment_id):
        return next(
            (
                item
                for item in self.attachments
                if item.appeal_id == appeal_id and item.id == attachment_id
            ),
            None,
        )

    async def get_crisis_contact(self, appeal_id):
        return self.contact if appeal_id == self.appeal.id else None

    async def upsert_rejection(self, rejection):
        self.rejection = rejection

    async def add_all(self, records):
        self.added.extend(records)
        self.status_history.extend(item for item in records if isinstance(item, StatusHistory))
        self.assignment_history.extend(
            item for item in records if isinstance(item, AssignmentHistory)
        )
        self.audits.extend(item for item in records if item.__class__.__name__ == "AuditLog")
        participant = next((item for item in records if isinstance(item, AppealParticipant)), None)
        if participant:
            self.primary = participant
        self._record_transfer_flush_states()

    async def add_audit(self, audit):
        self.audits.append(audit)

    async def commit(self):
        self._record_transfer_flush_states()
        self.commits += 1

    async def rollback(self):
        return None


class FakeAuthService:
    def __init__(self, users: dict[str, StaffUser]) -> None:
        self.users = users

    async def authenticate_access_token(self, token: str) -> StaffUser:
        user = self.users.get(token)
        if user is None:
            raise UnauthorizedError()
        return user


def _category() -> Category:
    return Category(
        id=uuid4(),
        slug="bullying-insults",
        name="Буллинг и оскорбления",
        description="Описание",
        is_active=True,
        sort_order=10,
    )


def _appeal(category: Category | None = None, *, crisis: bool = False) -> Appeal:
    now = datetime.now(UTC) - timedelta(hours=30)
    appeal = Appeal(
        id=uuid4(),
        track_digest=b"x" * 32,
        applicant_type=ApplicantType.STUDENT,
        category_id=category.id if category else None,
        status=AppealStatus.NEW,
        priority=AppealPriority.STANDARD,
        crisis_flag=crisis,
        return_count=0,
    )
    appeal.created_at = now
    appeal.updated_at = now
    return appeal


def _staff(role: StaffRole) -> StaffUser:
    return StaffUser(
        id=uuid4(),
        login=f"{role.value}-{uuid4()}",
        password_hash="argon2",
        role=role,
        is_active=True,
        display_name=role.value,
    )


def _service(test_settings, repository: FakeOperatorRepository, *, path: Path | None = None):
    settings = (
        test_settings.model_copy(update={"attachment_storage_path": path})
        if path is not None
        else test_settings
    )
    return OperatorService(cast(OperatorRepository, repository), settings)


def _eligible_expert(repository: FakeOperatorRepository, *, load: int = 0, capacity: int = 5):
    expert = _staff(StaffRole.EXPERT)
    repository.staff[expert.id] = expert
    repository.routing = [
        RoutingCandidateRecord(
            expert,
            ExpertProfile(staff_user_id=expert.id, max_active_appeals=capacity),
            SpecialistGroup(id=uuid4(), slug="psychologists", name="Психологи", is_active=True),
            load,
        )
    ]
    return expert


async def test_operator_queue_derives_overdue_and_supports_filters(test_settings) -> None:
    category = _category()
    appeal = _appeal(category, crisis=True)
    repository = FakeOperatorRepository(appeal, category)
    service = _service(test_settings, repository)

    queue = await service.queue(
        operator_role=StaffRole.OPERATOR,
        status=None,
        priority=AppealPriority.STANDARD,
        category_id=category.id,
        crisis=True,
        assigned=False,
        page=1,
        page_size=25,
    )

    assert queue.items[0].crisis_flag is True
    assert queue.items[0].is_overdue is True
    assert queue.counters.crisis == queue.counters.new == queue.counters.overdue == 1


def test_queue_order_is_crisis_then_urgent_then_oldest() -> None:
    category = _category()
    old_standard = _appeal(category)
    old_standard.created_at = datetime.now(UTC) - timedelta(hours=4)
    new_urgent = _appeal(category)
    new_urgent.priority = AppealPriority.URGENT
    new_urgent.created_at = datetime.now(UTC) - timedelta(hours=1)
    old_urgent = _appeal(category)
    old_urgent.priority = AppealPriority.URGENT
    old_urgent.created_at = datetime.now(UTC) - timedelta(hours=2)
    crisis = _appeal(category, crisis=True)
    crisis.priority = AppealPriority.LOW

    ordered = sorted([old_standard, new_urgent, crisis, old_urgent], key=operator_queue_sort_key)
    assert ordered == [crisis, old_urgent, new_urgent, old_standard]


def test_applicant_status_copy_does_not_expose_staff_identity() -> None:
    assigned = applicant_status_text(AppealStatus.ASSIGNED, ApplicantType.STUDENT)
    rejected = applicant_status_text(AppealStatus.REJECTED, ApplicantType.PARENT)
    assert "специалист" in assigned.casefold()
    assert "имя" not in assigned.casefold()
    assert "оператор" not in rejected.casefold()


async def test_operator_detail_decrypts_only_explicit_triage_fields(test_settings) -> None:
    category = _category()
    appeal = _appeal(category)
    repository = FakeOperatorRepository(appeal, category)
    crypto = ContentCrypto(test_settings.content_encryption_key.get_secret_value())
    repository.content = AppealContent(
        appeal_id=appeal.id,
        encrypted_content=crypto.encrypt_text(
            "Секретное описание", aad=appeal_content_aad(appeal.id)
        ),
        key_version=1,
    )
    repository.intake = AppealIntakeAnswer(
        appeal_id=appeal.id,
        encrypted_payload=crypto.encrypt_json(
            {"where": "в школе"}, aad=intake_answers_aad(appeal.id)
        ),
        key_version=1,
    )
    detail = await _service(test_settings, repository).detail(
        appeal.id, operator_role=StaffRole.OPERATOR
    )

    assert detail.description == "Секретное описание"
    assert detail.intake_answers == {"where": "в школе"}
    fields = set(detail.model_dump())
    assert {"track_digest", "crisis_contact", "messages", "internal_notes"}.isdisjoint(fields)
    with pytest.raises(ForbiddenError):
        await _service(test_settings, repository).detail(appeal.id, operator_role=StaffRole.ADMIN)


async def test_triage_changes_are_audited_and_accept_timestamp_is_set_once(test_settings) -> None:
    first_category = _category()
    second_category = Category(
        id=uuid4(), slug="legal", name="Правовой вопрос", is_active=True, sort_order=20
    )
    appeal = _appeal(first_category)
    repository = FakeOperatorRepository(appeal, first_category)
    repository.categories[second_category.id] = second_category
    service = _service(test_settings, repository)
    first_time = datetime.now(UTC)
    second_time = first_time + timedelta(hours=1)

    await service.triage(
        appeal.id,
        OperatorTriageRequest(category_id=second_category.id, priority=AppealPriority.URGENT),
        operator_id=uuid4(),
        operator_role=StaffRole.OPERATOR,
        now=first_time,
    )
    await service.triage(
        appeal.id,
        OperatorTriageRequest(priority=AppealPriority.LOW),
        operator_id=uuid4(),
        operator_role=StaffRole.OPERATOR,
        now=second_time,
    )

    assert appeal.category_id == second_category.id
    assert appeal.priority is AppealPriority.LOW
    assert appeal.operator_accepted_at == first_time
    assert {audit.action for audit in repository.audits} == {
        "operator.category_changed",
        "operator.priority_changed",
    }


async def test_valid_assignment_writes_participant_and_histories(test_settings) -> None:
    category = _category()
    appeal = _appeal(category)
    repository = FakeOperatorRepository(appeal, category)
    expert = _eligible_expert(repository)

    await _service(test_settings, repository).assign(
        appeal.id,
        expert.id,
        operator_id=uuid4(),
        operator_role=StaffRole.OPERATOR,
    )

    assert appeal.status is AppealStatus.ASSIGNED
    assert appeal.assigned_expert_id == expert.id
    assert repository.primary is not None
    assert repository.primary.participant_role is AppealParticipantRole.PRIMARY
    assert len(repository.status_history) == 1
    assert len(repository.assignment_history) == 1
    assert repository.audits[-1].metadata_json == {
        "expert_id": str(expert.id),
        "category_id": str(category.id),
    }


async def test_returned_appeal_can_be_assigned_again(test_settings) -> None:
    category = _category()
    appeal = _appeal(category)
    appeal.status = AppealStatus.RETURNED
    repository = FakeOperatorRepository(appeal, category)
    expert = _eligible_expert(repository)

    await _service(test_settings, repository).assign(
        appeal.id,
        expert.id,
        operator_id=uuid4(),
        operator_role=StaffRole.OPERATOR,
    )

    assert appeal.status is AppealStatus.ASSIGNED
    assert repository.status_history[-1].from_status is AppealStatus.RETURNED


async def test_assignment_rejects_nonexpert_ineligible_and_over_capacity(test_settings) -> None:
    category = _category()
    appeal = _appeal(category)
    repository = FakeOperatorRepository(appeal, category)
    nonexpert = _staff(StaffRole.OPERATOR)
    repository.staff[nonexpert.id] = nonexpert
    service = _service(test_settings, repository)
    with pytest.raises(ValidationError):
        await service.assign(
            appeal.id,
            nonexpert.id,
            operator_id=uuid4(),
            operator_role=StaffRole.OPERATOR,
        )
    ineligible = _staff(StaffRole.EXPERT)
    repository.staff[ineligible.id] = ineligible
    with pytest.raises(ForbiddenError):
        await service.assign(
            appeal.id,
            ineligible.id,
            operator_id=uuid4(),
            operator_role=StaffRole.OPERATOR,
        )
    full = _eligible_expert(repository, load=5, capacity=5)
    with pytest.raises(ConflictError):
        await service.assign(
            appeal.id,
            full.id,
            operator_id=uuid4(),
            operator_role=StaffRole.OPERATOR,
        )


async def test_rejection_requires_reason_encrypts_it_and_audits_only_enum(test_settings) -> None:
    appeal = _appeal(_category())
    repository = FakeOperatorRepository(appeal)
    service = _service(test_settings, repository)
    with pytest.raises(ValidationError):
        await service.reject(
            appeal.id,
            kind=RejectionKind.SPAM,
            reason="  ",
            operator_id=uuid4(),
            operator_role=StaffRole.OPERATOR,
        )
    reason = "Это обращение не относится к работе сервиса"
    await service.reject(
        appeal.id,
        kind=RejectionKind.OUTSIDE_COMPETENCE,
        reason=reason,
        operator_id=uuid4(),
        operator_role=StaffRole.OPERATOR,
    )
    assert appeal.status is AppealStatus.REJECTED
    assert reason.encode() not in repository.rejection.encrypted_reason
    crypto = ContentCrypto(test_settings.content_encryption_key.get_secret_value())
    assert (
        crypto.decrypt_text(
            repository.rejection.encrypted_reason, aad=rejection_reason_aad(appeal.id)
        )
        == reason
    )
    audit = repository.audits[-1]
    assert audit.metadata_json == {"rejection_kind": "outside_competence"}
    assert reason not in repr(audit.__dict__)


async def test_crisis_contact_is_separate_and_operator_only(test_settings) -> None:
    appeal = _appeal(crisis=True)
    repository = FakeOperatorRepository(appeal)
    crypto = ContentCrypto(test_settings.content_encryption_key.get_secret_value())
    repository.contact = CrisisContact(
        appeal_id=appeal.id,
        encrypted_contact=crypto.encrypt_text("safe contact", aad=crisis_contact_aad(appeal.id)),
        key_version=1,
    )
    service = _service(test_settings, repository)
    result = await service.crisis_contact(
        appeal.id,
        operator_id=uuid4(),
        operator_role=StaffRole.OPERATOR,
    )
    assert result.contact == "safe contact"
    assert repository.audits[-1].metadata_json is None
    for role in (StaffRole.EXPERT, StaffRole.ADMIN):
        with pytest.raises(ForbiddenError):
            await service.crisis_contact(appeal.id, operator_id=uuid4(), operator_role=role)
    appeal.crisis_flag = False
    with pytest.raises(ForbiddenError):
        await service.crisis_contact(
            appeal.id,
            operator_id=uuid4(),
            operator_role=StaffRole.OPERATOR,
        )


async def test_operator_retrieves_verified_decrypted_attachment(
    test_settings, tmp_path: Path
) -> None:
    appeal = _appeal()
    attachment_id = uuid4()
    settings = test_settings.model_copy(update={"attachment_storage_path": tmp_path})
    crypto = ContentCrypto(settings.content_encryption_key.get_secret_value())
    plaintext = b"sanitized-image"
    encrypted = crypto.encrypt_bytes(plaintext, aad=attachment_aad(appeal.id, attachment_id))
    storage = PrivateAttachmentStorage(tmp_path)
    storage_key = storage.write(encrypted)
    repository = FakeOperatorRepository(appeal)
    attachment = Attachment(
        id=attachment_id,
        appeal_id=appeal.id,
        storage_key=storage_key,
        mime_type="image/png",
        byte_size=len(encrypted),
        sha256_digest=hashlib.sha256(encrypted).digest(),
    )
    attachment.created_at = datetime.now(UTC)
    repository.attachments.append(attachment)
    service = _service(settings, repository, path=tmp_path)
    result = await service.attachment(appeal.id, attachment.id, operator_role=StaffRole.OPERATOR)
    assert result.body == plaintext
    assert result.mime_type == "image/png"
    assert str(tmp_path) not in result.safe_filename
    for role in (StaffRole.EXPERT, StaffRole.ADMIN):
        with pytest.raises(ForbiddenError):
            await service.attachment(appeal.id, attachment.id, operator_role=role)


async def test_operator_routes_enforce_401_403_and_operator_success(test_settings) -> None:
    appeal = _appeal()
    repository = FakeOperatorRepository(appeal)
    service = _service(test_settings, repository)
    users = {role.value: _staff(role) for role in StaffRole}
    app = create_app(test_settings)
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService(users)
    app.dependency_overrides[get_operator_service] = lambda: service
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unauthenticated = await client.get("/api/v1/operator/appeals")
        expert = await client.get(
            "/api/v1/operator/appeals", headers={"Authorization": "Bearer expert"}
        )
        admin = await client.get(
            f"/api/v1/operator/appeals/{appeal.id}",
            headers={"Authorization": "Bearer admin"},
        )
        operator = await client.get(
            "/api/v1/operator/appeals", headers={"Authorization": "Bearer operator"}
        )
    assert unauthenticated.status_code == 401
    assert expert.status_code == 403
    assert admin.status_code == 403
    assert operator.status_code == 200


async def test_return_explanation_is_decrypted_only_in_operator_detail(test_settings) -> None:
    appeal = _appeal(_category())
    appeal.status = AppealStatus.RETURNED
    repository = FakeOperatorRepository(appeal)
    crypto = ContentCrypto(test_settings.content_encryption_key.get_secret_value())
    explanation_id = uuid4()
    explanation = AppealReturnExplanation(
        id=explanation_id,
        appeal_id=appeal.id,
        return_number=1,
        encrypted_body=crypto.encrypt_text(
            "Не хватило конкретного плана",
            aad=return_explanation_aad(appeal.id, explanation_id),
        ),
        key_version=1,
    )
    explanation.created_at = datetime.now(UTC)
    repository.return_explanations.append(explanation)

    detail = await _service(test_settings, repository).detail(
        appeal.id, operator_role=StaffRole.OPERATOR
    )

    assert detail.return_explanations[0].body == "Не хватило конкретного плана"
    with pytest.raises(ForbiddenError):
        await _service(test_settings, repository).detail(appeal.id, operator_role=StaffRole.ADMIN)


def _transfer_record(
    repository: FakeOperatorRepository,
    requester: StaffUser,
    target: StaffUser | None,
    crypto: ContentCrypto,
) -> OperatorTransferRecord:
    transfer_id = uuid4()
    transfer = TransferRequest(
        id=transfer_id,
        appeal_id=repository.appeal.id,
        requested_by_staff_user_id=requester.id,
        requested_target_staff_user_id=target.id if target else None,
        encrypted_reason=crypto.encrypt_text(
            "Нужен другой профиль помощи",
            aad=transfer_reason_aad(repository.appeal.id, transfer_id),
        ),
        key_version=1,
        status=TransferRequestStatus.PENDING,
    )
    transfer.created_at = datetime.now(UTC)
    return OperatorTransferRecord(transfer, repository.appeal, requester, target)


async def test_operator_approves_transfer_and_updates_assignment_history(test_settings) -> None:
    category = _category()
    appeal = _appeal(category)
    appeal.status = AppealStatus.IN_PROGRESS
    requester = _staff(StaffRole.EXPERT)
    appeal.assigned_expert_id = requester.id
    repository = FakeOperatorRepository(appeal, category)
    repository.staff[requester.id] = requester
    repository.primary = AppealParticipant(
        id=uuid4(),
        appeal_id=appeal.id,
        staff_user_id=requester.id,
        participant_role=AppealParticipantRole.PRIMARY,
        is_active=True,
    )
    target = _eligible_expert(repository)
    crypto = ContentCrypto(test_settings.content_encryption_key.get_secret_value())
    record = _transfer_record(repository, requester, target, crypto)
    repository.transfer_records.append(record)
    service = _service(test_settings, repository)

    listed = await service.transfer_requests(operator_role=StaffRole.OPERATOR)
    assert listed[0].reason == "Нужен другой профиль помощи"
    operator_id = uuid4()
    await service.resolve_transfer(
        record.transfer.id,
        approve=True,
        operator_id=operator_id,
        operator_role=StaffRole.OPERATOR,
    )

    assert record.transfer.status is TransferRequestStatus.APPROVED
    assert record.transfer.resolved_by_staff_user_id == operator_id
    assert record.transfer.resolved_at is not None
    assert appeal.assigned_expert_id == target.id
    assert repository.primary is not None
    assert repository.primary.staff_user_id == target.id
    assert repository.assignment_history[-1].from_expert_id == requester.id
    assert repository.assignment_history[-1].to_expert_id == target.id
    assert all(
        status is not TransferRequestStatus.PENDING or (resolver is None and resolved_at is None)
        for status, resolver, resolved_at in repository.flushed_transfer_states
    )
    assert "Нужен другой профиль" not in repr(repository.audits[-1].metadata_json)


async def test_operator_rejects_transfer_and_other_roles_cannot_resolve(test_settings) -> None:
    category = _category()
    appeal = _appeal(category)
    requester = _staff(StaffRole.EXPERT)
    target = _staff(StaffRole.EXPERT)
    repository = FakeOperatorRepository(appeal, category)
    crypto = ContentCrypto(test_settings.content_encryption_key.get_secret_value())
    record = _transfer_record(repository, requester, target, crypto)
    repository.transfer_records.append(record)
    service = _service(test_settings, repository)

    for role in (StaffRole.EXPERT, StaffRole.ADMIN):
        with pytest.raises(ForbiddenError):
            await service.resolve_transfer(
                record.transfer.id,
                approve=False,
                operator_id=uuid4(),
                operator_role=role,
            )
    operator_id = uuid4()
    await service.resolve_transfer(
        record.transfer.id,
        approve=False,
        operator_id=operator_id,
        operator_role=StaffRole.OPERATOR,
    )
    assert record.transfer.status is TransferRequestStatus.REJECTED
    assert record.transfer.resolved_by_staff_user_id == operator_id
    assert record.transfer.resolved_at is not None
    assert all(
        status is not TransferRequestStatus.PENDING or (resolver is None and resolved_at is None)
        for status, resolver, resolved_at in repository.flushed_transfer_states
    )


async def test_complaint_is_decrypted_for_operator_and_denied_to_expert_admin(
    test_settings,
) -> None:
    appeal = _appeal()
    repository = FakeOperatorRepository(appeal)
    crypto = ContentCrypto(test_settings.content_encryption_key.get_secret_value())
    complaint_id = uuid4()
    complaint = StaffComplaint(
        id=complaint_id,
        appeal_id=appeal.id,
        encrypted_body=crypto.encrypt_text(
            "Жалоба на сервис", aad=complaint_body_aad(appeal.id, complaint_id)
        ),
        key_version=1,
    )
    complaint.created_at = datetime.now(UTC)
    repository.complaints.append(complaint)
    service = _service(test_settings, repository)

    result = await service.complaints(appeal.id, operator_role=StaffRole.OPERATOR)
    assert result[0].body == "Жалоба на сервис"
    for role in (StaffRole.EXPERT, StaffRole.ADMIN):
        with pytest.raises(ForbiddenError):
            await service.complaints(appeal.id, operator_role=role)


async def test_operator_selects_replacement_for_cannot_take_request(test_settings) -> None:
    category = _category()
    appeal = _appeal(category)
    appeal.status = AppealStatus.ASSIGNED
    requester = _staff(StaffRole.EXPERT)
    appeal.assigned_expert_id = requester.id
    repository = FakeOperatorRepository(appeal, category)
    repository.staff[requester.id] = requester
    repository.primary = AppealParticipant(
        id=uuid4(),
        appeal_id=appeal.id,
        staff_user_id=requester.id,
        participant_role=AppealParticipantRole.PRIMARY,
        is_active=True,
    )
    replacement = _eligible_expert(repository)
    crypto = ContentCrypto(test_settings.content_encryption_key.get_secret_value())
    record = _transfer_record(repository, requester, None, crypto)
    repository.transfer_records.append(record)
    service = _service(test_settings, repository)

    pending = await service.transfer_requests(operator_role=StaffRole.OPERATOR)
    assert pending[0].request_kind == "cannot_take"
    assert pending[0].target_expert_id is None
    assert [item.expert_id for item in pending[0].eligible_experts] == [replacement.id]
    for role in (StaffRole.EXPERT, StaffRole.ADMIN):
        with pytest.raises(ForbiddenError):
            await service.transfer_requests(operator_role=role)
        with pytest.raises(ForbiddenError):
            await service.resolve_transfer(
                record.transfer.id,
                approve=True,
                replacement_expert_id=replacement.id,
                operator_id=requester.id,
                operator_role=role,
            )

    await service.resolve_transfer(
        record.transfer.id,
        approve=True,
        replacement_expert_id=replacement.id,
        operator_id=uuid4(),
        operator_role=StaffRole.OPERATOR,
    )

    assert record.transfer.status is TransferRequestStatus.APPROVED
    assert appeal.assigned_expert_id == replacement.id
    assert repository.primary.staff_user_id == replacement.id
    assert repository.assignment_history[-1].from_expert_id == requester.id
    assert repository.assignment_history[-1].to_expert_id == replacement.id
    assert repository.commits == 1
    assert all(
        status is not TransferRequestStatus.PENDING or (resolver is None and resolved_at is None)
        for status, resolver, resolved_at in repository.flushed_transfer_states
    )


async def test_rejected_cannot_take_request_keeps_current_assignment(test_settings) -> None:
    category = _category()
    appeal = _appeal(category)
    appeal.status = AppealStatus.IN_PROGRESS
    requester = _staff(StaffRole.EXPERT)
    appeal.assigned_expert_id = requester.id
    repository = FakeOperatorRepository(appeal, category)
    primary = AppealParticipant(
        id=uuid4(),
        appeal_id=appeal.id,
        staff_user_id=requester.id,
        participant_role=AppealParticipantRole.PRIMARY,
        is_active=True,
    )
    repository.primary = primary
    crypto = ContentCrypto(test_settings.content_encryption_key.get_secret_value())
    record = _transfer_record(repository, requester, None, crypto)
    repository.transfer_records.append(record)

    await _service(test_settings, repository).resolve_transfer(
        record.transfer.id,
        approve=False,
        operator_id=uuid4(),
        operator_role=StaffRole.OPERATOR,
    )

    assert record.transfer.status is TransferRequestStatus.REJECTED
    assert appeal.assigned_expert_id == requester.id
    assert repository.primary is primary
    assert primary.is_active is True
    assert repository.assignment_history == []


async def test_failed_transfer_validation_leaves_request_and_assignment_unchanged(
    test_settings,
) -> None:
    category = _category()
    appeal = _appeal(category)
    appeal.status = AppealStatus.ASSIGNED
    requester = _staff(StaffRole.EXPERT)
    appeal.assigned_expert_id = requester.id
    repository = FakeOperatorRepository(appeal, category)
    primary = AppealParticipant(
        id=uuid4(),
        appeal_id=appeal.id,
        staff_user_id=requester.id,
        participant_role=AppealParticipantRole.PRIMARY,
        is_active=True,
    )
    repository.primary = primary
    crypto = ContentCrypto(test_settings.content_encryption_key.get_secret_value())
    record = _transfer_record(repository, requester, None, crypto)
    repository.transfer_records.append(record)

    with pytest.raises(ValidationError, match="replacement expert"):
        await _service(test_settings, repository).resolve_transfer(
            record.transfer.id,
            approve=True,
            operator_id=uuid4(),
            operator_role=StaffRole.OPERATOR,
        )

    assert record.transfer.status is TransferRequestStatus.PENDING
    assert record.transfer.resolved_by_staff_user_id is None
    assert record.transfer.resolved_at is None
    assert appeal.assigned_expert_id == requester.id
    assert repository.primary is primary
    assert primary.is_active is True
    assert repository.assignment_history == []
    assert repository.commits == 0
