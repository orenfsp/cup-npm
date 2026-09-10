from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr, model_validator

from app.db.models.enums import (
    AppealPriority,
    AppealStatus,
    RejectionKind,
    TransferRequestStatus,
)


class OperatorCategory(BaseModel):
    id: UUID
    slug: str
    name: str


class QueueCounters(BaseModel):
    crisis: int
    new: int
    returned: int
    overdue: int


class OperatorQueueItem(BaseModel):
    id: UUID
    applicant_type: str
    category: OperatorCategory | None
    status: AppealStatus
    priority: AppealPriority
    crisis_flag: bool
    assigned: bool
    created_at: datetime
    waiting_since: datetime
    waiting_seconds: int
    is_overdue: bool


class OperatorQueueResponse(BaseModel):
    items: list[OperatorQueueItem]
    total: int
    page: int
    page_size: int
    counters: QueueCounters


class AttachmentDescriptor(BaseModel):
    id: UUID
    mime_type: str
    byte_size: int
    created_at: datetime


class OperatorStatusHistoryItem(BaseModel):
    from_status: AppealStatus | None
    to_status: AppealStatus
    created_at: datetime


class OperatorAssignmentHistoryItem(BaseModel):
    from_expert_id: UUID | None
    to_expert_id: UUID | None
    created_at: datetime


class OperatorReturnExplanation(BaseModel):
    id: UUID
    return_number: int
    body: str
    created_at: datetime


class AssignedExpert(BaseModel):
    id: UUID
    display_name: str


class RoutingCandidate(BaseModel):
    expert_id: UUID
    display_name: str
    groups: list[str]
    current_load: int
    capacity: int
    available: bool


class RoutingRecommendation(BaseModel):
    state: str
    recommended_expert: RoutingCandidate | None
    candidates: list[RoutingCandidate]
    reason: str


class OperatorAppealDetail(BaseModel):
    id: UUID
    applicant_type: str
    description: str | None
    intake_answers: dict[str, str | bool | list[str]]
    category: OperatorCategory | None
    suggested_category: OperatorCategory | None
    status: AppealStatus
    priority: AppealPriority
    crisis_flag: bool
    created_at: datetime
    updated_at: datetime
    operator_accepted_at: datetime | None
    waiting_seconds: int
    is_overdue: bool
    attachments: list[AttachmentDescriptor]
    assigned_expert: AssignedExpert | None
    status_history: list[OperatorStatusHistoryItem]
    assignment_history: list[OperatorAssignmentHistoryItem]
    return_explanations: list[OperatorReturnExplanation]
    routing: RoutingRecommendation


class OperatorTriageRequest(BaseModel):
    category_id: UUID | None = None
    priority: AppealPriority | None = None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set & {"category_id", "priority"}:
            raise ValueError("Provide a category or priority change")
        if "category_id" in self.model_fields_set and self.category_id is None:
            raise ValueError("Category cannot be cleared during triage")
        return self


class AssignmentRequest(BaseModel):
    expert_id: UUID


class RejectionRequest(BaseModel):
    kind: RejectionKind
    reason: SecretStr = Field(min_length=1, max_length=2000)


class ActionResponse(BaseModel):
    status: str = "ok"


class CrisisContactResponse(BaseModel):
    contact: str


class OperatorReferenceResponse(BaseModel):
    categories: list[OperatorCategory]


class OperatorTransferRequestItem(BaseModel):
    id: UUID
    appeal_id: UUID
    requester_display_name: str
    target_expert_id: UUID | None
    target_display_name: str | None
    reason: str
    status: TransferRequestStatus
    created_at: datetime
    request_kind: Literal["targeted_transfer", "cannot_take"]
    eligible_experts: list[RoutingCandidate]


class TransferResolutionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    replacement_expert_id: UUID | None = None

    @model_validator(mode="after")
    def reject_does_not_select_replacement(self) -> Self:
        if self.decision == "reject" and self.replacement_expert_id is not None:
            raise ValueError("A rejected request cannot select a replacement expert")
        return self


class OperatorComplaintItem(BaseModel):
    id: UUID
    body: str
    created_at: datetime
