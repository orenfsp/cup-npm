from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr

from app.db.models.enums import (
    AppealParticipantRole,
    AppealPriority,
    AppealStatus,
    MessageAuthorType,
    TransferRequestStatus,
)
from app.modules.operator.schemas import AttachmentDescriptor, OperatorCategory, RoutingCandidate


class ExpertQueueItem(BaseModel):
    id: UUID
    applicant_type: str
    category: OperatorCategory | None
    status: AppealStatus
    priority: AppealPriority
    crisis_flag: bool
    created_at: datetime
    waiting_seconds: int


class ExpertQueueResponse(BaseModel):
    items: list[ExpertQueueItem]
    total: int
    page: int
    page_size: int


class ExpertMessage(BaseModel):
    id: UUID
    author_type: MessageAuthorType
    author_label: str
    body: str
    created_at: datetime


class ExpertNote(BaseModel):
    id: UUID
    author_staff_user_id: UUID
    author_label: str
    body: str
    created_at: datetime


class ExpertParticipant(BaseModel):
    staff_user_id: UUID
    display_name: str
    role: AppealParticipantRole
    joined_at: datetime


class ExpertTransferState(BaseModel):
    id: UUID
    target_staff_user_id: UUID | None
    status: TransferRequestStatus
    created_at: datetime
    resolved_at: datetime | None


class ExpertAppealDetail(BaseModel):
    id: UUID
    applicant_type: str
    category: OperatorCategory | None
    status: AppealStatus
    priority: AppealPriority
    crisis_flag: bool
    description: str | None
    intake_answers: dict[str, str | bool | list[str]]
    attachments: list[AttachmentDescriptor]
    messages: list[ExpertMessage]
    internal_notes: list[ExpertNote]
    participants: list[ExpertParticipant]
    transfers: list[ExpertTransferState]
    collaboration_candidates: list[RoutingCandidate]
    is_primary: bool
    created_at: datetime
    updated_at: datetime


class MessageRequest(BaseModel):
    body: SecretStr = Field(min_length=1, max_length=5000)


class ClarificationRequest(BaseModel):
    message: SecretStr | None = Field(default=None, max_length=5000)


class NoteRequest(BaseModel):
    body: SecretStr = Field(min_length=1, max_length=5000)


class CollaborationRequest(BaseModel):
    expert_id: UUID
    reason: SecretStr = Field(min_length=1, max_length=2000)


class TransferCreateRequest(BaseModel):
    target_expert_id: UUID
    reason: SecretStr = Field(min_length=1, max_length=2000)


class CannotTakeRequest(BaseModel):
    reason: SecretStr = Field(min_length=1, max_length=2000)


class ActionResponse(BaseModel):
    status: str = "ok"


class ComposerLockResponse(BaseModel):
    status: str
    expires_in_seconds: int
