import asyncio
import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.core.config import Settings
from app.core.crypto import ContentCrypto
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    InfrastructureError,
    NotFoundError,
    ValidationError,
)
from app.db.models import (
    AppealParticipant,
    AppealRejection,
    AssignmentHistory,
    AuditLog,
    StatusHistory,
)
from app.db.models.enums import (
    AppealParticipantRole,
    AppealPriority,
    AppealStatus,
    StaffRole,
    TransferRequestStatus,
)
from app.db.repositories.operator import OperatorDetailRecord, OperatorRepository
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
from app.modules.attachments.storage import PrivateAttachmentStorage
from app.modules.auth.policy import AccessPolicy
from app.modules.operator.schemas import (
    ActionResponse,
    AssignedExpert,
    AttachmentDescriptor,
    CrisisContactResponse,
    OperatorAppealDetail,
    OperatorAssignmentHistoryItem,
    OperatorCategory,
    OperatorComplaintItem,
    OperatorQueueItem,
    OperatorQueueResponse,
    OperatorReferenceResponse,
    OperatorReturnExplanation,
    OperatorStatusHistoryItem,
    OperatorTransferRequestItem,
    OperatorTriageRequest,
    QueueCounters,
)
from app.modules.operator.transitions import require_operator_transition, require_triage_status
from app.modules.routing.service import RoutingService


@dataclass(frozen=True, slots=True)
class RetrievedAttachment:
    body: bytes
    mime_type: str
    safe_filename: str


def operator_queue_sort_key(appeal):
    priority_rank = {
        AppealPriority.URGENT: 0,
        AppealPriority.STANDARD: 1,
        AppealPriority.LOW: 2,
    }
    return (
        0 if appeal.crisis_flag else 1,
        priority_rank[appeal.priority],
        appeal.created_at,
        str(appeal.id),
    )


class OperatorService:
    """Authorized triage path; chat and internal-note models are intentionally absent."""

    def __init__(self, repository: OperatorRepository, settings: Settings) -> None:
        encryption_key = settings.content_encryption_key
        if encryption_key is None or not encryption_key.get_secret_value():
            raise InfrastructureError("Sensitive-content encryption is not configured.")
        self._repository = repository
        self._settings = settings
        self._crypto = ContentCrypto(encryption_key.get_secret_value())
        self._routing = RoutingService(repository)
        self._storage = PrivateAttachmentStorage(settings.attachment_storage_path)

    async def queue(
        self,
        *,
        operator_role: StaffRole,
        status,
        priority,
        category_id,
        crisis,
        assigned,
        page: int,
        page_size: int,
        now: datetime | None = None,
    ) -> OperatorQueueResponse:
        self._require_operator(operator_role)
        current_time = now or datetime.now(UTC)
        rows, total = await self._repository.list_queue(
            status=status,
            priority=priority,
            category_id=category_id,
            crisis=crisis,
            assigned=assigned,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        counter_rows = await self._repository.queue_counter_rows()
        rows = sorted(rows, key=lambda row: operator_queue_sort_key(row.appeal))
        overdue_delta = timedelta(hours=self._settings.operator_overdue_hours)
        return OperatorQueueResponse(
            items=[
                self._queue_item(row.appeal, row.category, current_time, overdue_delta)
                for row in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
            counters=QueueCounters(
                crisis=sum(item.crisis_flag for item in counter_rows),
                new=sum(item.status is AppealStatus.NEW for item in counter_rows),
                returned=sum(item.status is AppealStatus.RETURNED for item in counter_rows),
                overdue=sum(
                    current_time - item.created_at >= overdue_delta for item in counter_rows
                ),
            ),
        )

    async def reference(self, *, operator_role: StaffRole) -> OperatorReferenceResponse:
        self._require_operator(operator_role)
        categories = await self._repository.list_active_categories()
        return OperatorReferenceResponse(
            categories=[self._category(category) for category in categories]
        )

    async def detail(
        self,
        appeal_id: UUID,
        *,
        operator_role: StaffRole,
        now: datetime | None = None,
    ) -> OperatorAppealDetail:
        self._require_sensitive_operator(operator_role)
        record = await self._repository.get_detail(appeal_id)
        if record is None:
            raise NotFoundError("Appeal not found.")
        return await self._detail_response(record, now or datetime.now(UTC))

    async def triage(
        self,
        appeal_id: UUID,
        payload: OperatorTriageRequest,
        *,
        operator_id: UUID,
        operator_role: StaffRole,
        now: datetime | None = None,
    ) -> ActionResponse:
        self._require_operator(operator_role)
        appeal = await self._locked_triage_appeal(appeal_id)
        current_time = now or datetime.now(UTC)
        self._accept_once(appeal, current_time)
        audits: list[object] = []
        if "category_id" in payload.model_fields_set and payload.category_id != appeal.category_id:
            category = await self._repository.get_category(payload.category_id)
            if category is None or not category.is_active:
                raise ValidationError("Choose an active category.")
            previous = appeal.category_id
            appeal.category_id = category.id
            audits.append(
                self._audit(
                    operator_id,
                    "operator.category_changed",
                    appeal.id,
                    {
                        "from_category_id": str(previous) if previous else None,
                        "to_category_id": str(category.id),
                    },
                )
            )
        if payload.priority is not None and payload.priority is not appeal.priority:
            previous_priority = appeal.priority
            appeal.priority = payload.priority
            audits.append(
                self._audit(
                    operator_id,
                    "operator.priority_changed",
                    appeal.id,
                    {
                        "from_priority": previous_priority.value,
                        "to_priority": payload.priority.value,
                    },
                )
            )
        if audits:
            await self._repository.add_all(audits)
        await self._repository.commit()
        return ActionResponse()

    async def assign(
        self,
        appeal_id: UUID,
        expert_id: UUID,
        *,
        operator_id: UUID,
        operator_role: StaffRole,
        now: datetime | None = None,
    ) -> ActionResponse:
        self._require_operator(operator_role)
        appeal = await self._locked_triage_appeal(appeal_id)
        require_operator_transition(appeal.status, AppealStatus.ASSIGNED)
        if appeal.category_id is None:
            raise ValidationError("Choose a category before assigning an expert.")
        expert = await self._repository.get_staff(expert_id)
        if expert is None or expert.role is not StaffRole.EXPERT or not expert.is_active:
            raise ValidationError("Choose an active expert account.")
        recommendation = await self._routing.recommend(appeal.category_id)
        candidate = next(
            (item for item in recommendation.candidates if item.expert_id == expert_id), None
        )
        if candidate is None:
            raise ForbiddenError("The expert is not eligible for the selected category.")
        if not candidate.available:
            raise ConflictError("The expert is at configured capacity.")

        current_time = now or datetime.now(UTC)
        previous_status = appeal.status
        previous_expert = appeal.assigned_expert_id
        primary = await self._repository.current_primary(appeal.id)
        if primary is not None and primary.staff_user_id != expert_id:
            primary.is_active = False
            primary.left_at = current_time
            primary = None
        records: list[object] = []
        if primary is None:
            records.append(
                AppealParticipant(
                    id=uuid4(),
                    appeal_id=appeal.id,
                    staff_user_id=expert_id,
                    participant_role=AppealParticipantRole.PRIMARY,
                    is_active=True,
                    joined_at=current_time,
                )
            )
        appeal.assigned_expert_id = expert_id
        appeal.status = AppealStatus.ASSIGNED
        self._accept_once(appeal, current_time)
        records.extend(
            [
                AssignmentHistory(
                    id=uuid4(),
                    appeal_id=appeal.id,
                    from_expert_id=previous_expert,
                    to_expert_id=expert_id,
                    changed_by_staff_user_id=operator_id,
                ),
                StatusHistory(
                    id=uuid4(),
                    appeal_id=appeal.id,
                    from_status=previous_status,
                    to_status=AppealStatus.ASSIGNED,
                    changed_by_staff_user_id=operator_id,
                ),
                self._audit(
                    operator_id,
                    "operator.appeal_assigned",
                    appeal.id,
                    {"expert_id": str(expert_id), "category_id": str(appeal.category_id)},
                ),
            ]
        )
        await self._repository.add_all(records)
        await self._repository.commit()
        return ActionResponse()

    async def reject(
        self,
        appeal_id: UUID,
        *,
        kind,
        reason: str,
        operator_id: UUID,
        operator_role: StaffRole,
        now: datetime | None = None,
    ) -> ActionResponse:
        self._require_operator(operator_role)
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ValidationError("A rejection explanation is required.")
        appeal = await self._locked_triage_appeal(appeal_id)
        require_operator_transition(appeal.status, AppealStatus.REJECTED)
        current_time = now or datetime.now(UTC)
        previous_status = appeal.status
        previous_expert = appeal.assigned_expert_id
        appeal.status = AppealStatus.REJECTED
        appeal.assigned_expert_id = None
        self._accept_once(appeal, current_time)
        primary = await self._repository.current_primary(appeal.id)
        if primary is not None:
            primary.is_active = False
            primary.left_at = current_time
        await self._repository.upsert_rejection(
            AppealRejection(
                appeal_id=appeal.id,
                kind=kind,
                encrypted_reason=self._crypto.encrypt_text(
                    normalized_reason, aad=rejection_reason_aad(appeal.id)
                ),
                key_version=self._crypto.key_version,
            )
        )
        records: list[object] = [
            StatusHistory(
                id=uuid4(),
                appeal_id=appeal.id,
                from_status=previous_status,
                to_status=AppealStatus.REJECTED,
                changed_by_staff_user_id=operator_id,
            ),
            self._audit(
                operator_id,
                "operator.appeal_rejected",
                appeal.id,
                {"rejection_kind": kind.value},
            ),
        ]
        if previous_expert is not None:
            records.append(
                AssignmentHistory(
                    id=uuid4(),
                    appeal_id=appeal.id,
                    from_expert_id=previous_expert,
                    to_expert_id=None,
                    changed_by_staff_user_id=operator_id,
                )
            )
        await self._repository.add_all(records)
        await self._repository.commit()
        return ActionResponse()

    async def crisis_contact(
        self,
        appeal_id: UUID,
        *,
        operator_id: UUID,
        operator_role: StaffRole,
    ) -> CrisisContactResponse:
        if not AccessPolicy.operator_may_read_crisis_contact(operator_role):
            raise ForbiddenError()
        appeal = await self._repository.get_appeal_for_update(appeal_id)
        if appeal is None:
            raise NotFoundError("Appeal not found.")
        if not appeal.crisis_flag:
            raise ForbiddenError("Crisis contact is available only for a crisis appeal.")
        contact = await self._repository.get_crisis_contact(appeal_id)
        if contact is None:
            raise NotFoundError("No crisis contact was submitted.")
        plaintext = self._crypto.decrypt_text(
            contact.encrypted_contact, aad=crisis_contact_aad(appeal_id)
        )
        await self._repository.add_audit(
            self._audit(operator_id, "operator.crisis_contact_accessed", appeal_id, None)
        )
        await self._repository.commit()
        return CrisisContactResponse(contact=plaintext)

    async def transfer_requests(
        self, *, operator_role: StaffRole
    ) -> list[OperatorTransferRequestItem]:
        self._require_operator(operator_role)
        rows = await self._repository.list_pending_transfers()
        result: list[OperatorTransferRequestItem] = []
        for row in rows:
            routing = await self._routing.recommend(row.appeal.category_id)
            result.append(
                OperatorTransferRequestItem(
                    id=row.transfer.id,
                    appeal_id=row.appeal.id,
                    requester_display_name=row.requester.display_name,
                    target_expert_id=row.transfer.requested_target_staff_user_id,
                    target_display_name=row.target.display_name if row.target else None,
                    reason=self._transfer_reason(row.transfer),
                    status=row.transfer.status,
                    created_at=row.transfer.created_at,
                    request_kind=(
                        "targeted_transfer"
                        if row.transfer.requested_target_staff_user_id is not None
                        else "cannot_take"
                    ),
                    eligible_experts=[
                        candidate
                        for candidate in routing.candidates
                        if candidate.expert_id != row.appeal.assigned_expert_id
                    ],
                )
            )
        return result

    async def resolve_transfer(
        self,
        transfer_id: UUID,
        *,
        approve: bool,
        replacement_expert_id: UUID | None = None,
        operator_id: UUID,
        operator_role: StaffRole,
        now: datetime | None = None,
    ) -> ActionResponse:
        if not AccessPolicy.operator_may_resolve_transfer(operator_role):
            raise ForbiddenError()
        transfer = await self._repository.get_transfer_for_update(transfer_id)
        if transfer is None:
            raise NotFoundError("Transfer request not found.")
        if transfer.status is not TransferRequestStatus.PENDING:
            raise ConflictError("Transfer request has already been resolved.")
        current_time = now or datetime.now(UTC)
        if not approve:
            transfer.status = TransferRequestStatus.REJECTED
            transfer.resolved_by_staff_user_id = operator_id
            transfer.resolved_at = current_time
            await self._repository.add_all(
                [
                    self._audit(
                        operator_id,
                        (
                            "operator.transfer_rejected"
                            if transfer.requested_target_staff_user_id is not None
                            else "operator.reassignment_rejected"
                        ),
                        transfer.appeal_id,
                        {"transfer_request_id": str(transfer.id)},
                    )
                ]
            )
            await self._repository.commit()
            return ActionResponse()

        appeal = await self._repository.get_appeal_for_update(transfer.appeal_id)
        if appeal is None:
            raise NotFoundError("Appeal not found.")
        if appeal.status not in {
            AppealStatus.ASSIGNED,
            AppealStatus.IN_PROGRESS,
            AppealStatus.NEEDS_CLARIFICATION,
        }:
            raise ConflictError("Appeal cannot be transferred in its current status.")
        target_id = replacement_expert_id or transfer.requested_target_staff_user_id
        if target_id is None:
            raise ValidationError("Choose an eligible replacement expert.")
        if target_id == appeal.assigned_expert_id:
            raise ValidationError("Choose an expert other than the current primary.")
        target = await self._repository.get_staff(target_id)
        if target is None or target.role is not StaffRole.EXPERT or not target.is_active:
            raise ValidationError("Transfer target is not an active expert.")
        if appeal.category_id is None:
            raise ValidationError("Choose a category before approving transfer.")
        recommendation = await self._routing.recommend(appeal.category_id)
        candidate = next(
            (item for item in recommendation.candidates if item.expert_id == target_id), None
        )
        if candidate is None:
            raise ForbiddenError("Transfer target is not eligible for the category.")
        target_participant = await self._repository.active_participant(appeal.id, target_id)
        if not candidate.available and target_participant is None:
            raise ConflictError("Transfer target is at configured capacity.")

        previous_expert = appeal.assigned_expert_id
        previous_status = appeal.status
        primary = await self._repository.current_primary(appeal.id)

        # Keep the request valid at every flush boundary. In particular, the primary
        # participant must be flushed inactive before a replacement primary can be
        # inserted, and PostgreSQL correctly rejects resolution metadata on a request
        # whose status is still pending.
        transfer.status = TransferRequestStatus.APPROVED
        transfer.resolved_by_staff_user_id = operator_id
        transfer.resolved_at = current_time
        if primary is not None and primary.staff_user_id != target_id:
            primary.is_active = False
            primary.left_at = current_time
            await self._repository.flush()
        records: list[object] = []
        if target_participant is None:
            records.append(
                AppealParticipant(
                    id=uuid4(),
                    appeal_id=appeal.id,
                    staff_user_id=target_id,
                    participant_role=AppealParticipantRole.PRIMARY,
                    is_active=True,
                    joined_at=current_time,
                )
            )
        else:
            target_participant.participant_role = AppealParticipantRole.PRIMARY
        appeal.assigned_expert_id = target_id
        appeal.status = AppealStatus.IN_PROGRESS
        records.append(
            AssignmentHistory(
                id=uuid4(),
                appeal_id=appeal.id,
                from_expert_id=previous_expert,
                to_expert_id=target_id,
                changed_by_staff_user_id=operator_id,
                reason=f"approved transfer request {transfer.id}",
            )
        )
        if previous_status is not AppealStatus.IN_PROGRESS:
            records.append(
                StatusHistory(
                    id=uuid4(),
                    appeal_id=appeal.id,
                    from_status=previous_status,
                    to_status=AppealStatus.IN_PROGRESS,
                    changed_by_staff_user_id=operator_id,
                )
            )
        records.append(
            self._audit(
                operator_id,
                (
                    "operator.transfer_approved"
                    if transfer.requested_target_staff_user_id is not None
                    else "operator.reassignment_approved"
                ),
                appeal.id,
                {"transfer_request_id": str(transfer.id), "expert_id": str(target_id)},
            )
        )
        await self._repository.add_all(records)
        await self._repository.commit()
        return ActionResponse()

    async def complaints(
        self, appeal_id: UUID, *, operator_role: StaffRole
    ) -> list[OperatorComplaintItem]:
        if not AccessPolicy.operator_may_read_complaint(operator_role):
            raise ForbiddenError()
        if await self._repository.get_appeal_for_update(appeal_id) is None:
            raise NotFoundError("Appeal not found.")
        rows = await self._repository.list_complaints(appeal_id)
        return [
            OperatorComplaintItem(
                id=item.id,
                body=self._crypto.decrypt_text(
                    item.encrypted_body, aad=complaint_body_aad(appeal_id, item.id)
                ),
                created_at=item.created_at,
            )
            for item in rows
        ]

    async def attachment(
        self,
        appeal_id: UUID,
        attachment_id: UUID,
        *,
        operator_role: StaffRole,
    ) -> RetrievedAttachment:
        self._require_sensitive_operator(operator_role)
        attachment = await self._repository.get_attachment(appeal_id, attachment_id)
        if attachment is None:
            raise NotFoundError("Attachment not found.")
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

    async def _locked_triage_appeal(self, appeal_id: UUID):
        appeal = await self._repository.get_appeal_for_update(appeal_id)
        if appeal is None:
            raise NotFoundError("Appeal not found.")
        require_triage_status(appeal.status)
        return appeal

    async def _detail_response(
        self, record: OperatorDetailRecord, current_time: datetime
    ) -> OperatorAppealDetail:
        appeal = record.appeal
        description = (
            self._crypto.decrypt_text(
                record.content.encrypted_content, aad=appeal_content_aad(appeal.id)
            )
            if record.content
            else None
        )
        intake_value = (
            self._crypto.decrypt_json(
                record.intake.encrypted_payload, aad=intake_answers_aad(appeal.id)
            )
            if record.intake
            else {}
        )
        intake = (
            {
                str(key): value
                for key, value in intake_value.items()
                if isinstance(value, (str, bool))
                or (
                    isinstance(value, list)
                    and all(isinstance(choice, str) for choice in value)
                )
            }
            if isinstance(intake_value, dict)
            else {}
        )
        overdue = timedelta(hours=self._settings.operator_overdue_hours)
        return OperatorAppealDetail(
            id=appeal.id,
            applicant_type=appeal.applicant_type,
            description=description,
            intake_answers=intake,
            category=self._category(record.category) if record.category else None,
            suggested_category=(
                self._category(record.suggested_category) if record.suggested_category else None
            ),
            status=appeal.status,
            priority=appeal.priority,
            crisis_flag=appeal.crisis_flag,
            created_at=appeal.created_at,
            updated_at=appeal.updated_at,
            operator_accepted_at=appeal.operator_accepted_at,
            waiting_seconds=max(0, int((current_time - appeal.created_at).total_seconds())),
            is_overdue=current_time - appeal.created_at >= overdue,
            attachments=[
                AttachmentDescriptor(
                    id=item.id,
                    mime_type=item.mime_type,
                    byte_size=item.byte_size,
                    created_at=item.created_at,
                )
                for item in record.attachments
            ],
            assigned_expert=(
                AssignedExpert(
                    id=record.assigned_expert.id,
                    display_name=record.assigned_expert.display_name,
                )
                if record.assigned_expert
                else None
            ),
            status_history=[
                OperatorStatusHistoryItem(
                    from_status=item.from_status,
                    to_status=item.to_status,
                    created_at=item.created_at,
                )
                for item in record.status_history
            ],
            assignment_history=[
                OperatorAssignmentHistoryItem(
                    from_expert_id=item.from_expert_id,
                    to_expert_id=item.to_expert_id,
                    created_at=item.created_at,
                )
                for item in record.assignment_history
            ],
            return_explanations=[
                OperatorReturnExplanation(
                    id=item.id,
                    return_number=item.return_number,
                    body=self._crypto.decrypt_text(
                        item.encrypted_body,
                        aad=return_explanation_aad(appeal.id, item.id),
                    ),
                    created_at=item.created_at,
                )
                for item in record.return_explanations
            ],
            routing=await self._routing.recommend(appeal.category_id),
        )

    def _transfer_reason(self, transfer) -> str:
        return self._crypto.decrypt_text(
            transfer.encrypted_reason,
            aad=transfer_reason_aad(transfer.appeal_id, transfer.id),
        )

    @staticmethod
    def _queue_item(appeal, category, now, overdue_delta):
        waiting_seconds = max(0, int((now - appeal.created_at).total_seconds()))
        return OperatorQueueItem(
            id=appeal.id,
            applicant_type=appeal.applicant_type,
            category=OperatorService._category(category) if category else None,
            status=appeal.status,
            priority=appeal.priority,
            crisis_flag=appeal.crisis_flag,
            assigned=appeal.assigned_expert_id is not None,
            created_at=appeal.created_at,
            waiting_since=appeal.created_at,
            waiting_seconds=waiting_seconds,
            is_overdue=now - appeal.created_at >= overdue_delta,
        )

    @staticmethod
    def _category(category):
        return OperatorCategory(id=category.id, slug=category.slug, name=category.name)

    @staticmethod
    def _accept_once(appeal, now: datetime) -> None:
        if appeal.operator_accepted_at is None:
            appeal.operator_accepted_at = now

    @staticmethod
    def _audit(actor_id: UUID, action: str, appeal_id: UUID, metadata):
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
    def _require_operator(role: StaffRole) -> None:
        if not AccessPolicy.operator_may_triage(role):
            raise ForbiddenError()

    @staticmethod
    def _require_sensitive_operator(role: StaffRole) -> None:
        if not AccessPolicy.operator_may_read_triage_content(role):
            raise ForbiddenError()
