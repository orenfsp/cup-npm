import asyncio
import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.config import Settings
from app.core.crypto import ContentCrypto
from app.core.errors import ConflictError, ForbiddenError, InfrastructureError, ValidationError
from app.db.models import (
    Appeal,
    AppealMessage,
    AppealParticipant,
    AuditLog,
    InternalNote,
    StatusHistory,
    TransferRequest,
)
from app.db.models.enums import (
    AppealParticipantRole,
    AppealStatus,
    MessageAuthorType,
    StaffRole,
    TransferRequestStatus,
)
from app.db.repositories.expert import ExpertDetailRecord, ExpertRepository
from app.modules.appeals.crypto_context import (
    appeal_content_aad,
    appeal_message_aad,
    attachment_aad,
    intake_answers_aad,
    internal_note_aad,
    transfer_reason_aad,
)
from app.modules.appeals.transitions import require_expert_transition
from app.modules.attachments.storage import PrivateAttachmentStorage
from app.modules.auth.policy import AccessPolicy
from app.modules.expert.composer_lock import ComposerLockService
from app.modules.expert.schemas import (
    ActionResponse,
    ComposerLockResponse,
    ExpertAppealDetail,
    ExpertMessage,
    ExpertNote,
    ExpertParticipant,
    ExpertQueueItem,
    ExpertQueueResponse,
    ExpertTransferState,
)
from app.modules.operator.schemas import AttachmentDescriptor, OperatorCategory
from app.modules.operator.service import RetrievedAttachment
from app.modules.routing.service import RoutingService


@dataclass(frozen=True, slots=True)
class ExpertServiceDependencies:
    repository: ExpertRepository
    routing: RoutingService
    composer_locks: ComposerLockService


class ExpertService:
    """All decrypted expert content is guarded by active appeal participation."""

    def __init__(self, dependencies: ExpertServiceDependencies, settings: Settings) -> None:
        encryption_key = settings.content_encryption_key
        if encryption_key is None or not encryption_key.get_secret_value():
            raise InfrastructureError("Sensitive-content encryption is not configured.")
        self._repository = dependencies.repository
        self._routing = dependencies.routing
        self._locks = dependencies.composer_locks
        self._crypto = ContentCrypto(encryption_key.get_secret_value())
        self._storage = PrivateAttachmentStorage(settings.attachment_storage_path)

    async def queue(
        self,
        expert_id: UUID,
        *,
        expert_role: StaffRole,
        status,
        priority,
        category_id,
        page: int,
        page_size: int,
        now: datetime | None = None,
    ) -> ExpertQueueResponse:
        self._require_expert(expert_role)
        current_time = now or datetime.now(UTC)
        rows, total = await self._repository.list_queue(
            expert_id,
            status=status,
            priority=priority,
            category_id=category_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return ExpertQueueResponse(
            items=[
                ExpertQueueItem(
                    id=row.appeal.id,
                    applicant_type=row.appeal.applicant_type,
                    category=(
                        OperatorCategory(
                            id=row.category.id,
                            slug=row.category.slug,
                            name=row.category.name,
                        )
                        if row.category
                        else None
                    ),
                    status=row.appeal.status,
                    priority=row.appeal.priority,
                    crisis_flag=row.appeal.crisis_flag,
                    created_at=row.appeal.created_at,
                    waiting_seconds=max(
                        0, int((current_time - row.appeal.created_at).total_seconds())
                    ),
                )
                for row in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def detail(
        self, appeal_id: UUID, expert_id: UUID, *, expert_role: StaffRole
    ) -> ExpertAppealDetail:
        self._require_expert(expert_role)
        record = await self._repository.get_detail(appeal_id, expert_id)
        if record is None:
            raise ForbiddenError("This appeal is not assigned or shared with you.")
        return await self._detail_response(record, expert_id)

    async def take_into_work(
        self,
        appeal_id: UUID,
        expert_id: UUID,
        *,
        expert_role: StaffRole,
        now: datetime | None = None,
    ) -> ActionResponse:
        appeal = await self._locked_appeal(appeal_id, expert_id, expert_role)
        require_expert_transition(appeal.status, AppealStatus.IN_PROGRESS)
        previous = appeal.status
        appeal.status = AppealStatus.IN_PROGRESS
        await self._repository.add_all(
            [
                StatusHistory(
                    id=uuid4(),
                    appeal_id=appeal.id,
                    from_status=previous,
                    to_status=AppealStatus.IN_PROGRESS,
                    changed_by_staff_user_id=expert_id,
                ),
                self._audit(expert_id, "expert.appeal_started", appeal.id),
            ]
        )
        await self._repository.commit()
        return ActionResponse()

    async def send_message(
        self,
        appeal_id: UUID,
        expert_id: UUID,
        body: str,
        *,
        expert_role: StaffRole,
        now: datetime | None = None,
    ) -> ActionResponse:
        appeal = await self._locked_appeal(appeal_id, expert_id, expert_role)
        await self._locks.require_owner(appeal_id, expert_id)
        if appeal.status not in {AppealStatus.IN_PROGRESS, AppealStatus.NEEDS_CLARIFICATION}:
            raise ConflictError("Messages can be sent only while the appeal is in progress.")
        message = self._specialist_message(appeal.id, expert_id, body)
        current_time = now or datetime.now(UTC)
        if appeal.first_specialist_response_at is None:
            appeal.first_specialist_response_at = current_time
        await self._repository.add_all([message])
        await self._repository.commit()
        return ActionResponse()

    async def request_clarification(
        self,
        appeal_id: UUID,
        expert_id: UUID,
        message: str | None,
        *,
        expert_role: StaffRole,
        now: datetime | None = None,
    ) -> ActionResponse:
        appeal = await self._locked_appeal(appeal_id, expert_id, expert_role)
        await self._locks.require_owner(appeal_id, expert_id)
        require_expert_transition(appeal.status, AppealStatus.NEEDS_CLARIFICATION)
        current_time = now or datetime.now(UTC)
        records: list[object] = []
        normalized = message.strip() if message else ""
        if normalized:
            records.append(self._specialist_message(appeal.id, expert_id, normalized))
            if appeal.first_specialist_response_at is None:
                appeal.first_specialist_response_at = current_time
        previous = appeal.status
        appeal.status = AppealStatus.NEEDS_CLARIFICATION
        records.extend(
            [
                StatusHistory(
                    id=uuid4(),
                    appeal_id=appeal.id,
                    from_status=previous,
                    to_status=AppealStatus.NEEDS_CLARIFICATION,
                    changed_by_staff_user_id=expert_id,
                ),
                self._audit(expert_id, "expert.clarification_requested", appeal.id),
            ]
        )
        await self._repository.add_all(records)
        await self._repository.commit()
        return ActionResponse()

    async def add_note(
        self,
        appeal_id: UUID,
        expert_id: UUID,
        body: str,
        *,
        expert_role: StaffRole,
    ) -> ActionResponse:
        await self._authorized_appeal(appeal_id, expert_id, expert_role)
        note = self._internal_note(appeal_id, expert_id, body)
        await self._repository.add_all([note])
        await self._repository.commit()
        return ActionResponse()

    async def notes(
        self, appeal_id: UUID, expert_id: UUID, *, expert_role: StaffRole
    ) -> list[ExpertNote]:
        self._require_expert(expert_role)
        rows = await self._repository.list_notes_for_participant(appeal_id, expert_id)
        if rows is None:
            raise ForbiddenError("This appeal is not assigned or shared with you.")
        return [self._note_response(note, author) for note, author in rows]

    async def add_coexecutor(
        self,
        appeal_id: UUID,
        expert_id: UUID,
        target_expert_id: UUID,
        reason: str,
        *,
        expert_role: StaffRole,
        now: datetime | None = None,
    ) -> ActionResponse:
        appeal = await self._locked_primary_appeal(appeal_id, expert_id, expert_role)
        if target_expert_id == expert_id:
            raise ValidationError("Choose another expert as coexecutor.")
        if await self._repository.active_participant(appeal.id, target_expert_id):
            raise ConflictError("The selected expert already participates in this appeal.")
        await self._eligible_active_target(appeal.category_id, target_expert_id)
        current_time = now or datetime.now(UTC)
        participant = AppealParticipant(
            id=uuid4(),
            appeal_id=appeal.id,
            staff_user_id=target_expert_id,
            participant_role=AppealParticipantRole.COEXECUTOR,
            is_active=True,
            joined_at=current_time,
        )
        # The collaboration reason is sensitive free text, so it is retained only as an
        # encrypted internal note. Audit metadata contains identifiers only.
        note = self._internal_note(appeal.id, expert_id, reason)
        await self._repository.add_all(
            [
                participant,
                note,
                self._audit(
                    expert_id,
                    "expert.coexecutor_added",
                    appeal.id,
                    {"coexecutor_id": str(target_expert_id)},
                ),
            ]
        )
        await self._repository.commit()
        return ActionResponse()

    async def request_transfer(
        self,
        appeal_id: UUID,
        expert_id: UUID,
        target_expert_id: UUID,
        reason: str,
        *,
        expert_role: StaffRole,
    ) -> ActionResponse:
        appeal = await self._locked_primary_appeal(appeal_id, expert_id, expert_role)
        if target_expert_id == expert_id:
            raise ValidationError("Choose another expert for transfer.")
        await self._eligible_active_target(appeal.category_id, target_expert_id)
        return await self._create_transfer_request(
            appeal, expert_id, reason, target_expert_id=target_expert_id
        )

    async def request_reassignment(
        self,
        appeal_id: UUID,
        expert_id: UUID,
        reason: str,
        *,
        expert_role: StaffRole,
    ) -> ActionResponse:
        """Ask an operator to choose a replacement without abandoning responsibility."""

        appeal = await self._locked_primary_appeal(appeal_id, expert_id, expert_role)
        return await self._create_transfer_request(appeal, expert_id, reason, target_expert_id=None)

    async def _create_transfer_request(
        self,
        appeal: Appeal,
        expert_id: UUID,
        reason: str,
        *,
        target_expert_id: UUID | None,
    ) -> ActionResponse:
        if appeal.status not in {
            AppealStatus.ASSIGNED,
            AppealStatus.IN_PROGRESS,
            AppealStatus.NEEDS_CLARIFICATION,
        }:
            raise ConflictError("A transfer cannot be requested in the current status.")
        if await self._repository.has_pending_transfer(appeal.id):
            raise ConflictError("This appeal already has a pending transfer request.")
        request_id = uuid4()
        normalized_reason = self._required_text(reason, "A transfer reason is required.")
        transfer = TransferRequest(
            id=request_id,
            appeal_id=appeal.id,
            requested_by_staff_user_id=expert_id,
            requested_target_staff_user_id=target_expert_id,
            encrypted_reason=self._crypto.encrypt_text(
                normalized_reason, aad=transfer_reason_aad(appeal.id, request_id)
            ),
            key_version=self._crypto.key_version,
            status=TransferRequestStatus.PENDING,
        )
        await self._repository.add_all(
            [
                transfer,
                self._audit(
                    expert_id,
                    (
                        "expert.transfer_requested"
                        if target_expert_id is not None
                        else "expert.reassignment_requested"
                    ),
                    appeal.id,
                    {"transfer_request_id": str(request_id)},
                ),
            ]
        )
        await self._repository.commit()
        return ActionResponse()

    async def prepare_recommendations(
        self,
        appeal_id: UUID,
        expert_id: UUID,
        body: str,
        *,
        expert_role: StaffRole,
        now: datetime | None = None,
    ) -> ActionResponse:
        appeal = await self._locked_appeal(appeal_id, expert_id, expert_role)
        await self._locks.require_owner(appeal_id, expert_id)
        require_expert_transition(appeal.status, AppealStatus.ANSWER_READY)
        current_time = now or datetime.now(UTC)
        previous = appeal.status
        appeal.status = AppealStatus.ANSWER_READY
        if appeal.answer_ready_at is None:
            appeal.answer_ready_at = current_time
        if appeal.first_specialist_response_at is None:
            appeal.first_specialist_response_at = current_time
        await self._repository.add_all(
            [
                self._specialist_message(appeal.id, expert_id, body),
                StatusHistory(
                    id=uuid4(),
                    appeal_id=appeal.id,
                    from_status=previous,
                    to_status=AppealStatus.ANSWER_READY,
                    changed_by_staff_user_id=expert_id,
                ),
                self._audit(expert_id, "expert.recommendations_ready", appeal.id),
            ]
        )
        await self._repository.commit()
        return ActionResponse()

    async def attachment(
        self,
        appeal_id: UUID,
        attachment_id: UUID,
        expert_id: UUID,
        *,
        expert_role: StaffRole,
    ) -> RetrievedAttachment:
        self._require_expert(expert_role)
        attachment = await self._repository.get_attachment_for_participant(
            appeal_id, attachment_id, expert_id
        )
        if attachment is None:
            raise ForbiddenError("This attachment is not available to you.")
        encrypted = await asyncio.to_thread(self._storage.read, attachment.storage_key)
        if not hmac.compare_digest(hashlib.sha256(encrypted).digest(), attachment.sha256_digest):
            raise ConflictError("Attachment integrity verification failed.")
        body = self._crypto.decrypt_bytes(encrypted, aad=attachment_aad(appeal_id, attachment.id))
        extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(
            attachment.mime_type, "bin"
        )
        return RetrievedAttachment(
            body=body,
            mime_type=attachment.mime_type,
            safe_filename=f"attachment-{attachment.id}.{extension}",
        )

    async def acquire_composer_lock(
        self, appeal_id: UUID, expert_id: UUID, *, expert_role: StaffRole
    ) -> ComposerLockResponse:
        await self._authorized_appeal(appeal_id, expert_id, expert_role)
        ttl = await self._locks.acquire(appeal_id, expert_id)
        return ComposerLockResponse(status="acquired", expires_in_seconds=ttl)

    async def heartbeat_composer_lock(
        self, appeal_id: UUID, expert_id: UUID, *, expert_role: StaffRole
    ) -> ComposerLockResponse:
        await self._authorized_appeal(appeal_id, expert_id, expert_role)
        ttl = await self._locks.heartbeat(appeal_id, expert_id)
        return ComposerLockResponse(status="renewed", expires_in_seconds=ttl)

    async def release_composer_lock(
        self, appeal_id: UUID, expert_id: UUID, *, expert_role: StaffRole
    ) -> ActionResponse:
        await self._authorized_appeal(appeal_id, expert_id, expert_role)
        await self._locks.release(appeal_id, expert_id)
        return ActionResponse()

    async def _detail_response(
        self, record: ExpertDetailRecord, expert_id: UUID
    ) -> ExpertAppealDetail:
        appeal = record.appeal
        primary = next(
            (
                participant
                for participant, _staff in record.participants
                if participant.participant_role is AppealParticipantRole.PRIMARY
            ),
            None,
        )
        routing = await self._routing.recommend(appeal.category_id)
        return ExpertAppealDetail(
            id=appeal.id,
            applicant_type=appeal.applicant_type,
            category=(
                OperatorCategory(
                    id=record.category.id,
                    slug=record.category.slug,
                    name=record.category.name,
                )
                if record.category
                else None
            ),
            status=appeal.status,
            priority=appeal.priority,
            crisis_flag=appeal.crisis_flag,
            description=(
                self._crypto.decrypt_text(
                    record.content.encrypted_content, aad=appeal_content_aad(appeal.id)
                )
                if record.content
                else None
            ),
            intake_answers=self._decrypt_intake(record),
            attachments=[
                AttachmentDescriptor(
                    id=item.id,
                    mime_type=item.mime_type,
                    byte_size=item.byte_size,
                    created_at=item.created_at,
                )
                for item in record.attachments
            ],
            messages=[self._message_response(item, author) for item, author in record.messages],
            internal_notes=[self._note_response(item, author) for item, author in record.notes],
            participants=[
                ExpertParticipant(
                    staff_user_id=participant.staff_user_id,
                    display_name=staff.display_name,
                    role=participant.participant_role,
                    joined_at=participant.joined_at,
                )
                for participant, staff in record.participants
            ],
            transfers=[
                ExpertTransferState(
                    id=item.id,
                    target_staff_user_id=item.requested_target_staff_user_id,
                    status=item.status,
                    created_at=item.created_at,
                    resolved_at=item.resolved_at,
                )
                for item in record.transfers
            ],
            collaboration_candidates=[
                item for item in routing.candidates if item.expert_id != expert_id
            ],
            is_primary=primary is not None and primary.staff_user_id == expert_id,
            created_at=appeal.created_at,
            updated_at=appeal.updated_at,
        )

    def _decrypt_intake(
        self, record: ExpertDetailRecord
    ) -> dict[str, str | bool | list[str]]:
        if record.intake is None:
            return {}
        value = self._crypto.decrypt_json(
            record.intake.encrypted_payload,
            aad=intake_answers_aad(record.appeal.id),
        )
        if not isinstance(value, dict):
            return {}
        return {
            str(key): item
            for key, item in value.items()
            if isinstance(item, (str, bool))
            or (isinstance(item, list) and all(isinstance(choice, str) for choice in item))
        }

    def _message_response(self, message: AppealMessage, author) -> ExpertMessage:
        return ExpertMessage(
            id=message.id,
            author_type=message.author_type,
            author_label=author.display_name if author else "Заявитель",
            body=self._crypto.decrypt_text(
                message.encrypted_body, aad=appeal_message_aad(message.appeal_id, message.id)
            ),
            created_at=message.created_at,
        )

    def _note_response(self, note: InternalNote, author) -> ExpertNote:
        return ExpertNote(
            id=note.id,
            author_staff_user_id=note.author_staff_user_id,
            author_label=author.display_name,
            body=self._crypto.decrypt_text(
                note.encrypted_body, aad=internal_note_aad(note.appeal_id, note.id)
            ),
            created_at=note.created_at,
        )

    def _specialist_message(self, appeal_id: UUID, expert_id: UUID, body: str) -> AppealMessage:
        normalized = self._required_text(body, "Message cannot be blank.")
        message_id = uuid4()
        return AppealMessage(
            id=message_id,
            appeal_id=appeal_id,
            author_type=MessageAuthorType.SPECIALIST,
            author_staff_user_id=expert_id,
            encrypted_body=self._crypto.encrypt_text(
                normalized, aad=appeal_message_aad(appeal_id, message_id)
            ),
            key_version=self._crypto.key_version,
        )

    def _internal_note(self, appeal_id: UUID, expert_id: UUID, body: str) -> InternalNote:
        normalized = self._required_text(body, "Internal note cannot be blank.")
        note_id = uuid4()
        return InternalNote(
            id=note_id,
            appeal_id=appeal_id,
            author_staff_user_id=expert_id,
            encrypted_body=self._crypto.encrypt_text(
                normalized, aad=internal_note_aad(appeal_id, note_id)
            ),
            key_version=self._crypto.key_version,
        )

    async def _authorized_appeal(self, appeal_id: UUID, expert_id: UUID, expert_role: StaffRole):
        self._require_expert(expert_role)
        appeal = await self._repository.get_appeal_for_participant(appeal_id, expert_id)
        if appeal is None:
            raise ForbiddenError("This appeal is not assigned or shared with you.")
        return appeal

    async def _locked_appeal(self, appeal_id: UUID, expert_id: UUID, expert_role: StaffRole):
        self._require_expert(expert_role)
        appeal = await self._repository.get_appeal_for_participant(
            appeal_id, expert_id, for_update=True
        )
        if appeal is None:
            raise ForbiddenError("This appeal is not assigned or shared with you.")
        return appeal

    async def _locked_primary_appeal(
        self, appeal_id: UUID, expert_id: UUID, expert_role: StaffRole
    ):
        appeal = await self._locked_appeal(appeal_id, expert_id, expert_role)
        primary = await self._repository.current_primary(appeal_id)
        if not AccessPolicy.primary_expert_may_manage_collaboration(
            expert_role,
            is_current_primary=primary is not None and primary.staff_user_id == expert_id,
        ):
            raise ForbiddenError("Only the primary specialist can manage collaboration.")
        return appeal

    async def _eligible_active_target(
        self, category_id: UUID | None, target_expert_id: UUID
    ) -> None:
        if category_id is None:
            raise ValidationError("The appeal needs a category before collaboration changes.")
        target = await self._repository.get_staff_for_update(target_expert_id)
        if target is None or target.role is not StaffRole.EXPERT or not target.is_active:
            raise ValidationError("Choose an active expert account.")
        routing = await self._routing.recommend(category_id)
        candidate = next(
            (item for item in routing.candidates if item.expert_id == target_expert_id), None
        )
        if candidate is None:
            raise ForbiddenError("The expert is not eligible for this appeal category.")
        if not candidate.available:
            raise ConflictError("The expert is at configured capacity.")

    @staticmethod
    def _required_text(value: str, message: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValidationError(message)
        return normalized

    @staticmethod
    def _audit(
        actor_id: UUID,
        action: str,
        appeal_id: UUID,
        metadata: dict[str, str] | None = None,
    ) -> AuditLog:
        return AuditLog(
            id=uuid4(),
            actor_staff_user_id=actor_id,
            action=action,
            entity_type="appeal",
            entity_id=appeal_id,
            reason=None,
            metadata_json=metadata,
        )

    @staticmethod
    def _require_expert(role: StaffRole) -> None:
        if not AccessPolicy.expert_may_use_workspace(role):
            raise ForbiddenError()
