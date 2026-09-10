import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.crypto import ContentCrypto
from app.core.errors import ConflictError, ForbiddenError, UnauthorizedError, ValidationError
from app.db.models import (
    Appeal,
    AppealMessage,
    AppealParticipant,
    Attachment,
    InternalNote,
    StaffUser,
    StatusHistory,
    TransferRequest,
)
from app.db.models.enums import (
    AppealParticipantRole,
    AppealPriority,
    AppealStatus,
    ApplicantType,
    MessageAuthorType,
    StaffRole,
    TransferRequestStatus,
)
from app.db.repositories.expert import ExpertQueueRecord, ExpertRepository
from app.main import create_app
from app.modules.appeals.crypto_context import (
    appeal_message_aad,
    attachment_aad,
    internal_note_aad,
    transfer_reason_aad,
)
from app.modules.attachments.storage import PrivateAttachmentStorage
from app.modules.auth.dependencies import get_auth_service
from app.modules.expert.composer_lock import ComposerLockService
from app.modules.expert.dependencies import get_expert_service
from app.modules.expert.service import ExpertService, ExpertServiceDependencies
from app.modules.operator.schemas import RoutingCandidate, RoutingRecommendation
from app.modules.routing.service import RoutingService


class FakeExpertRepository:
    def __init__(self, appeal: Appeal, expert_id: UUID) -> None:
        self.appeal = appeal
        self.participants = {expert_id}
        self.added: list[object] = []
        self.primary: AppealParticipant | None = None
        self.staff: dict[UUID, StaffUser] = {}
        self.attachments: list[Attachment] = []
        self.commits = 0

    async def get_appeal_for_participant(self, appeal_id, expert_id, *, for_update=False):
        del for_update
        if appeal_id == self.appeal.id and expert_id in self.participants:
            return self.appeal
        return None

    async def get_detail(self, appeal_id, expert_id):
        del appeal_id
        return None if expert_id not in self.participants else None

    async def list_queue(self, expert_id, **kwargs):
        del kwargs
        if expert_id not in self.participants:
            return [], 0
        return [ExpertQueueRecord(self.appeal, None)], 1

    async def add_all(self, records):
        self.added.extend(records)
        for record in records:
            if isinstance(record, AppealParticipant):
                self.participants.add(record.staff_user_id)

    async def commit(self):
        self.commits += 1

    async def current_primary(self, appeal_id):
        return self.primary if self.primary and self.primary.appeal_id == appeal_id else None

    async def active_participant(self, appeal_id, staff_id):
        if appeal_id == self.appeal.id and staff_id in self.participants:
            return self.primary if self.primary and self.primary.staff_user_id == staff_id else True
        return None

    async def get_staff_for_update(self, staff_id):
        return self.staff.get(staff_id)

    async def has_pending_transfer(self, appeal_id):
        del appeal_id
        return any(isinstance(item, TransferRequest) for item in self.added)

    async def get_attachment_for_participant(self, appeal_id, attachment_id, expert_id):
        if expert_id not in self.participants:
            return None
        return next(
            (
                item
                for item in self.attachments
                if item.appeal_id == appeal_id and item.id == attachment_id
            ),
            None,
        )


class FakeRouting:
    def __init__(self, response: RoutingRecommendation | None = None) -> None:
        self.response = response or RoutingRecommendation(
            state="no_eligible_expert",
            recommended_expert=None,
            candidates=[],
            reason="No candidates",
        )

    async def recommend(self, category_id):
        del category_id
        return self.response


class FakeLocks:
    def __init__(self) -> None:
        self.owner_checks = 0

    async def require_owner(self, appeal_id, expert_id):
        del appeal_id, expert_id
        self.owner_checks += 1


class DenyLocks(FakeLocks):
    async def require_owner(self, appeal_id, expert_id):
        del appeal_id, expert_id
        raise ConflictError("Composer lock required")


class FakeAuthService:
    def __init__(self, users: dict[str, StaffUser]) -> None:
        self.users = users

    async def authenticate_access_token(self, token: str) -> StaffUser:
        user = self.users.get(token)
        if user is None:
            raise UnauthorizedError()
        return user


def _appeal(status: AppealStatus = AppealStatus.IN_PROGRESS) -> Appeal:
    appeal = Appeal(
        id=uuid4(),
        track_digest=b"e" * 32,
        applicant_type=ApplicantType.STUDENT,
        status=status,
        priority=AppealPriority.STANDARD,
        crisis_flag=False,
    )
    appeal.created_at = datetime.now(UTC)
    appeal.updated_at = datetime.now(UTC)
    return appeal


def _service(test_settings, appeal: Appeal, expert_id: UUID, routing=None):
    repository = FakeExpertRepository(appeal, expert_id)
    locks = FakeLocks()
    dependencies = ExpertServiceDependencies(
        repository=cast(ExpertRepository, repository),
        routing=cast(RoutingService, routing or FakeRouting()),
        composer_locks=cast(ComposerLockService, locks),
    )
    return ExpertService(dependencies, test_settings), repository, locks


def _staff(role: StaffRole, *, staff_id: UUID | None = None) -> StaffUser:
    return StaffUser(
        id=staff_id or uuid4(),
        login=f"{role.value}-{uuid4()}",
        password_hash="argon2",
        role=role,
        is_active=True,
        display_name=role.value,
    )


async def test_expert_message_is_encrypted_and_first_response_is_set_once(test_settings) -> None:
    expert_id = uuid4()
    appeal = _appeal()
    service, repository, locks = _service(test_settings, appeal, expert_id)
    first_time = datetime(2026, 1, 1, tzinfo=UTC)
    second_time = datetime(2026, 1, 2, tzinfo=UTC)

    await service.send_message(
        appeal.id, expert_id, "Публичный ответ", expert_role=StaffRole.EXPERT, now=first_time
    )
    await service.send_message(
        appeal.id, expert_id, "Второй ответ", expert_role=StaffRole.EXPERT, now=second_time
    )

    messages = [item for item in repository.added if isinstance(item, AppealMessage)]
    crypto = ContentCrypto(test_settings.content_encryption_key.get_secret_value())
    assert len(messages) == 2
    assert "Публичный ответ".encode() not in messages[0].encrypted_body
    assert (
        crypto.decrypt_text(
            messages[0].encrypted_body, aad=appeal_message_aad(appeal.id, messages[0].id)
        )
        == "Публичный ответ"
    )
    assert messages[0].author_type is MessageAuthorType.SPECIALIST
    assert messages[0].author_staff_user_id == expert_id
    assert appeal.first_specialist_response_at == first_time
    assert locks.owner_checks == 2


async def test_actual_specialist_send_requires_composer_lock_ownership(test_settings) -> None:
    expert_id = uuid4()
    appeal = _appeal()
    repository = FakeExpertRepository(appeal, expert_id)
    dependencies = ExpertServiceDependencies(
        repository=cast(ExpertRepository, repository),
        routing=cast(RoutingService, FakeRouting()),
        composer_locks=cast(ComposerLockService, DenyLocks()),
    )
    service = ExpertService(dependencies, test_settings)

    with pytest.raises(ConflictError, match="Composer lock required"):
        await service.send_message(
            appeal.id,
            expert_id,
            "Сообщение без блокировки",
            expert_role=StaffRole.EXPERT,
        )

    assert not any(isinstance(item, AppealMessage) for item in repository.added)


async def test_unrelated_expert_cannot_read_or_write(test_settings) -> None:
    expert_id = uuid4()
    appeal = _appeal()
    service, _repository, _locks = _service(test_settings, appeal, expert_id)

    with pytest.raises(ForbiddenError):
        await service.send_message(
            appeal.id, uuid4(), "Не должен пройти", expert_role=StaffRole.EXPERT
        )
    with pytest.raises(ForbiddenError):
        await service.detail(appeal.id, uuid4(), expert_role=StaffRole.EXPERT)
    with pytest.raises(ForbiddenError):
        await service.add_note(appeal.id, expert_id, "note", expert_role=StaffRole.ADMIN)


async def test_internal_note_is_encrypted_and_separate_from_chat(test_settings) -> None:
    expert_id = uuid4()
    appeal = _appeal()
    service, repository, _locks = _service(test_settings, appeal, expert_id)

    await service.add_note(appeal.id, expert_id, "Только для команды", expert_role=StaffRole.EXPERT)

    notes = [item for item in repository.added if isinstance(item, InternalNote)]
    assert not [item for item in repository.added if isinstance(item, AppealMessage)]
    crypto = ContentCrypto(test_settings.content_encryption_key.get_secret_value())
    assert (
        crypto.decrypt_text(notes[0].encrypted_body, aad=internal_note_aad(appeal.id, notes[0].id))
        == "Только для команды"
    )


async def test_take_clarify_and_answer_ready_transitions(test_settings) -> None:
    expert_id = uuid4()
    appeal = _appeal(AppealStatus.ASSIGNED)
    service, repository, locks = _service(test_settings, appeal, expert_id)

    await service.take_into_work(appeal.id, expert_id, expert_role=StaffRole.EXPERT)
    assert appeal.status is AppealStatus.IN_PROGRESS
    await service.request_clarification(
        appeal.id, expert_id, "Уточните, пожалуйста", expert_role=StaffRole.EXPERT
    )
    assert appeal.status is AppealStatus.NEEDS_CLARIFICATION
    await service.prepare_recommendations(
        appeal.id, expert_id, "Итоговые рекомендации", expert_role=StaffRole.EXPERT
    )
    assert appeal.status is AppealStatus.ANSWER_READY
    assert appeal.answer_ready_at is not None
    transitions = [item for item in repository.added if isinstance(item, StatusHistory)]
    assert [item.to_status for item in transitions] == [
        AppealStatus.IN_PROGRESS,
        AppealStatus.NEEDS_CLARIFICATION,
        AppealStatus.ANSWER_READY,
    ]
    assert locks.owner_checks == 2


def test_expert_repository_queries_are_participant_scoped() -> None:
    source = Path(__file__).parents[1] / "app" / "db" / "repositories" / "expert.py"
    text = source.read_text(encoding="utf-8")
    assert "AppealParticipant.staff_user_id == expert_id" in text
    assert "AppealParticipant.is_active.is_(True)" in text


async def test_expert_routes_require_auth_and_exact_expert_role(test_settings) -> None:
    expert = _staff(StaffRole.EXPERT)
    service, _repository, _locks = _service(test_settings, _appeal(), expert.id)
    users = {
        "expert": expert,
        "operator": _staff(StaffRole.OPERATOR),
        "admin": _staff(StaffRole.ADMIN),
    }
    app = create_app(test_settings)
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService(users)
    app.dependency_overrides[get_expert_service] = lambda: service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unauthenticated = await client.get("/api/v1/expert/appeals")
        operator = await client.get(
            "/api/v1/expert/appeals", headers={"Authorization": "Bearer operator"}
        )
        admin = await client.get(
            "/api/v1/expert/appeals", headers={"Authorization": "Bearer admin"}
        )
        allowed = await client.get(
            "/api/v1/expert/appeals", headers={"Authorization": "Bearer expert"}
        )

    assert unauthenticated.status_code == 401
    assert operator.status_code == 403
    assert admin.status_code == 403
    assert allowed.status_code == 200


async def test_primary_adds_eligible_coexecutor_and_keeps_primary(test_settings) -> None:
    primary_id = uuid4()
    target = _staff(StaffRole.EXPERT)
    appeal = _appeal()
    appeal.category_id = uuid4()
    candidate = RoutingCandidate(
        expert_id=target.id,
        display_name=target.display_name,
        groups=["Психологи"],
        current_load=0,
        capacity=5,
        available=True,
    )
    routing = FakeRouting(
        RoutingRecommendation(
            state="available",
            recommended_expert=candidate,
            candidates=[candidate],
            reason="Eligible and available",
        )
    )
    service, repository, _locks = _service(test_settings, appeal, primary_id, routing)
    repository.primary = AppealParticipant(
        id=uuid4(),
        appeal_id=appeal.id,
        staff_user_id=primary_id,
        participant_role=AppealParticipantRole.PRIMARY,
        is_active=True,
    )
    repository.staff[target.id] = target

    await service.add_coexecutor(
        appeal.id,
        primary_id,
        target.id,
        "Нужна совместная экспертиза",
        expert_role=StaffRole.EXPERT,
    )

    participant = next(item for item in repository.added if isinstance(item, AppealParticipant))
    assert repository.primary.participant_role is AppealParticipantRole.PRIMARY
    assert participant.staff_user_id == target.id
    assert participant.participant_role is AppealParticipantRole.COEXECUTOR
    assert target.id in repository.participants


async def test_transfer_request_reason_is_encrypted(test_settings) -> None:
    primary_id = uuid4()
    target = _staff(StaffRole.EXPERT)
    appeal = _appeal()
    appeal.category_id = uuid4()
    candidate = RoutingCandidate(
        expert_id=target.id,
        display_name=target.display_name,
        groups=["Психологи"],
        current_load=1,
        capacity=5,
        available=True,
    )
    routing = FakeRouting(
        RoutingRecommendation(
            state="available",
            recommended_expert=candidate,
            candidates=[candidate],
            reason="Eligible and available",
        )
    )
    service, repository, _locks = _service(test_settings, appeal, primary_id, routing)
    repository.primary = AppealParticipant(
        id=uuid4(),
        appeal_id=appeal.id,
        staff_user_id=primary_id,
        participant_role=AppealParticipantRole.PRIMARY,
        is_active=True,
    )
    repository.staff[target.id] = target

    await service.request_transfer(
        appeal.id,
        primary_id,
        target.id,
        "Требуется другой профиль",
        expert_role=StaffRole.EXPERT,
    )

    transfer = next(item for item in repository.added if isinstance(item, TransferRequest))
    crypto = ContentCrypto(test_settings.content_encryption_key.get_secret_value())
    assert (
        crypto.decrypt_text(
            transfer.encrypted_reason,
            aad=transfer_reason_aad(appeal.id, transfer.id),
        )
        == "Требуется другой профиль"
    )


async def test_cannot_take_requires_reason_and_keeps_current_assignment(test_settings) -> None:
    primary_id = uuid4()
    appeal = _appeal(AppealStatus.ASSIGNED)
    appeal.assigned_expert_id = primary_id
    service, repository, _locks = _service(test_settings, appeal, primary_id)
    repository.primary = AppealParticipant(
        id=uuid4(),
        appeal_id=appeal.id,
        staff_user_id=primary_id,
        participant_role=AppealParticipantRole.PRIMARY,
        is_active=True,
    )

    with pytest.raises(ValidationError):
        await service.request_reassignment(
            appeal.id, primary_id, "  ", expert_role=StaffRole.EXPERT
        )
    await service.request_reassignment(
        appeal.id,
        primary_id,
        "Нет нужной специализации",
        expert_role=StaffRole.EXPERT,
    )

    transfer = next(item for item in repository.added if isinstance(item, TransferRequest))
    crypto = ContentCrypto(test_settings.content_encryption_key.get_secret_value())
    assert transfer.requested_target_staff_user_id is None
    assert transfer.status is TransferRequestStatus.PENDING
    assert "Нет нужной специализации".encode() not in transfer.encrypted_reason
    assert (
        crypto.decrypt_text(
            transfer.encrypted_reason,
            aad=transfer_reason_aad(appeal.id, transfer.id),
        )
        == "Нет нужной специализации"
    )
    assert appeal.assigned_expert_id == primary_id
    assert repository.primary.is_active is True
    assert appeal.status is AppealStatus.ASSIGNED


async def test_expert_attachment_requires_participation_and_decrypts(
    test_settings, tmp_path: Path
) -> None:
    expert_id = uuid4()
    appeal = _appeal()
    settings = test_settings.model_copy(update={"attachment_storage_path": tmp_path})
    service, repository, _locks = _service(settings, appeal, expert_id)
    attachment_id = uuid4()
    crypto = ContentCrypto(settings.content_encryption_key.get_secret_value())
    plaintext = b"sanitized-image"
    encrypted = crypto.encrypt_bytes(plaintext, aad=attachment_aad(appeal.id, attachment_id))
    storage_key = PrivateAttachmentStorage(tmp_path).write(encrypted)
    attachment = Attachment(
        id=attachment_id,
        appeal_id=appeal.id,
        storage_key=storage_key,
        mime_type="image/png",
        byte_size=len(encrypted),
        sha256_digest=hashlib.sha256(encrypted).digest(),
    )
    repository.attachments.append(attachment)

    result = await service.attachment(
        appeal.id,
        attachment.id,
        expert_id,
        expert_role=StaffRole.EXPERT,
    )
    assert result.body == plaintext
    with pytest.raises(ForbiddenError):
        await service.attachment(
            appeal.id,
            attachment.id,
            uuid4(),
            expert_role=StaffRole.EXPERT,
        )
    with pytest.raises(ForbiddenError):
        await service.attachment(
            appeal.id,
            attachment.id,
            expert_id,
            expert_role=StaffRole.ADMIN,
        )
