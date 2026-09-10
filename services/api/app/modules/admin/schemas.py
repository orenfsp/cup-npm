from datetime import date, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

from app.db.models.enums import (
    AppealPriority,
    AppealStatus,
    ApplicantTone,
    IntakeFieldType,
    StaffRole,
)

Slug = Annotated[str, Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")]


def _email(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) > 320 or normalized.count("@") != 1:
        raise ValueError("Enter a valid email address")
    local, domain = normalized.split("@", 1)
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise ValueError("Enter a valid email address")
    return normalized


class StaffCreateRequest(BaseModel):
    login: str = Field(min_length=2, max_length=100)
    email: str
    display_name: str = Field(min_length=1, max_length=200)
    role: StaffRole
    public_specialist_label: str | None = Field(default=None, max_length=120)
    max_active_appeals: int = Field(default=10, ge=1, le=1000)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _email(value)

    @model_validator(mode="after")
    def validate_expert_fields(self) -> Self:
        if self.role is StaffRole.EXPERT and not (
            self.public_specialist_label and self.public_specialist_label.strip()
        ):
            raise ValueError("Expert specialization is required")
        if self.role is not StaffRole.EXPERT and self.public_specialist_label:
            raise ValueError("Specialization is only available for experts")
        return self


class StaffUpdateRequest(BaseModel):
    email: str | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    role: StaffRole | None = None
    is_active: bool | None = None
    public_specialist_label: str | None = Field(default=None, max_length=120)
    max_active_appeals: int | None = Field(default=None, ge=1, le=1000)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return _email(value) if value is not None else None


class StaffAdminItem(BaseModel):
    id: UUID
    login: str
    email: str | None
    display_name: str
    role: StaffRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None
    public_specialist_label: str | None
    max_active_appeals: int | None
    active_appeals: int
    group_ids: list[UUID]
    password_configured: bool


class StaffCreateResult(BaseModel):
    """One-time provisioning secret; never use this schema for list/detail responses."""

    staff: StaffAdminItem
    temporary_password: str


class InvitationResult(BaseModel):
    staff: StaffAdminItem
    email_sent: bool
    message: str


class PasswordSetupRequest(BaseModel):
    token: SecretStr = Field(min_length=32, max_length=500)
    password: SecretStr = Field(min_length=12, max_length=200)


class PasswordSetupResponse(BaseModel):
    status: Literal["password_set"] = "password_set"


class ApplicantTypeRequest(BaseModel):
    code: Slug
    label: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    tone: ApplicantTone
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=100000)


class ApplicantTypeUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    tone: ApplicantTone | None = None
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100000)


class ApplicantTypeItem(ApplicantTypeRequest):
    id: UUID


class CategoryRequest(BaseModel):
    slug: Slug
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=100000)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100000)


class CategoryItem(CategoryRequest):
    id: UUID


class IntakeQuestionRequest(BaseModel):
    code: Slug
    label: str = Field(min_length=1, max_length=300)
    help_text: str | None = Field(default=None, max_length=2000)
    field_type: IntakeFieldType
    options: list[str] = Field(default_factory=list, max_length=30)
    required: bool = False
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=100000)

    @field_validator("options")
    @classmethod
    def normalize_options(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if any(not item or len(item) > 200 for item in normalized):
            raise ValueError("Choice options must be 1–200 characters")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Choice options must be unique")
        return normalized

    @model_validator(mode="after")
    def validate_choice_options(self) -> Self:
        is_choice = self.field_type in {
            IntakeFieldType.SINGLE_CHOICE,
            IntakeFieldType.MULTI_CHOICE,
        }
        if is_choice and len(self.options) < 2:
            raise ValueError("Choice questions require at least two options")
        if not is_choice and self.options:
            raise ValueError("Only choice questions may define options")
        return self


class IntakeQuestionUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=300)
    help_text: str | None = Field(default=None, max_length=2000)
    field_type: IntakeFieldType | None = None
    options: list[str] | None = Field(default=None, max_length=30)
    required: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100000)


class IntakeQuestionItem(IntakeQuestionRequest):
    id: UUID
    category_ids: list[UUID] = Field(default_factory=list)


class QuestionMappingItem(BaseModel):
    question_id: UUID
    required_override: bool | None = None
    sort_order: int = Field(default=0, ge=0, le=100000)


class CategoryQuestionMappingRequest(BaseModel):
    questions: list[QuestionMappingItem] = Field(max_length=100)

    @field_validator("questions")
    @classmethod
    def unique_questions(cls, value: list[QuestionMappingItem]) -> list[QuestionMappingItem]:
        if len({item.question_id for item in value}) != len(value):
            raise ValueError("A question may only be attached once")
        return value


class GroupRequest(BaseModel):
    slug: Slug
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class GroupItem(GroupRequest):
    id: UUID
    member_ids: list[UUID]
    active_experts: int
    available_experts: int
    active_load: int
    total_capacity: int


class GroupMembershipRequest(BaseModel):
    expert_ids: list[UUID] = Field(max_length=500)

    @field_validator("expert_ids")
    @classmethod
    def unique_experts(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("An expert may only be included once")
        return value


class RoutingItem(BaseModel):
    category_id: UUID
    group_ids: list[UUID]


class RoutingUpdateRequest(BaseModel):
    group_ids: list[UUID] = Field(max_length=100)


class CrisisRuleRequest(BaseModel):
    phrase: str = Field(min_length=1, max_length=300)
    is_active: bool = True
    allow_compact_match: bool = False
    sort_order: int = Field(default=0, ge=0, le=100000)


class CrisisRuleUpdate(BaseModel):
    phrase: str | None = Field(default=None, min_length=1, max_length=300)
    is_active: bool | None = None
    allow_compact_match: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100000)


class CrisisRuleItem(CrisisRuleRequest):
    id: UUID
    normalized_phrase: str


class CrisisRuleTestRequest(BaseModel):
    text: SecretStr = Field(min_length=1, max_length=10000)


class CrisisRuleMatch(BaseModel):
    id: UUID
    phrase: str


class CrisisRuleTestResponse(BaseModel):
    crisis_detected: bool
    matched_rules: list[CrisisRuleMatch]


class SupportResourceRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    phone: str | None = Field(default=None, max_length=60)
    url: str | None = Field(default=None, max_length=500)
    region: str | None = Field(default=None, max_length=120)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=100000)

    @model_validator(mode="after")
    def require_contact(self) -> Self:
        if not (self.phone and self.phone.strip()) and not (self.url and self.url.strip()):
            raise ValueError("Provide a phone number or URL")
        return self


class SupportResourceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    phone: str | None = Field(default=None, max_length=60)
    url: str | None = Field(default=None, max_length=500)
    region: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100000)


class SupportResourceItem(SupportResourceRequest):
    id: UUID


class SafeSettingItem(BaseModel):
    key: str
    value: str | int
    editable: Literal[False] = False
    source: Literal["environment"] = "environment"


class SafeSettingsResponse(BaseModel):
    settings: list[SafeSettingItem]
    secret_settings_excluded: bool = True


class SavedResponse(BaseModel):
    status: Literal["saved"] = "saved"


class AdminAppealItem(BaseModel):
    id: UUID
    applicant_type: str
    category_id: UUID | None
    category_name: str | None
    status: AppealStatus
    priority: AppealPriority
    crisis_flag: bool
    assigned_expert_id: UUID | None
    assigned_expert_display_name: str | None
    created_at: datetime
    updated_at: datetime
    operator_accepted_at: datetime | None
    first_specialist_response_at: datetime | None
    answer_ready_at: datetime | None
    completed_at: datetime | None


class AdminAppealPage(BaseModel):
    items: list[AdminAppealItem]
    total: int
    page: int
    page_size: int


class AdminAppealInterventionRequest(BaseModel):
    status: AppealStatus | None = None
    priority: AppealPriority | None = None
    assigned_expert_id: UUID | None = None
    reason: SecretStr = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set & {"status", "priority", "assigned_expert_id"}:
            raise ValueError("Provide a status, priority, or assigned expert change")
        return self


class AuditItem(BaseModel):
    id: UUID
    actor_staff_user_id: UUID | None
    actor_display_name: str | None
    action: str
    entity_type: str
    entity_id: UUID | None
    reason: str | None
    metadata: dict[str, object] | None
    created_at: datetime


class AuditPage(BaseModel):
    items: list[AuditItem]
    total: int
    page: int
    page_size: int


class AnalyticsPoint(BaseModel):
    key: str
    count: int


class AnalyticsDay(BaseModel):
    date: date
    count: int


class WorkloadItem(BaseModel):
    staff_user_id: UUID
    display_name: str
    role: StaffRole
    active_appeals: int
    capacity: int | None


class AnalyticsResponse(BaseModel):
    date_from: date
    date_to: date
    total: int
    new: int
    active: int
    completed: int
    urgent_share: float | None
    returned_share: float | None
    avg_operator_acceptance_seconds: float | None
    avg_first_response_seconds: float | None
    avg_resolution_seconds: float | None
    by_category: list[AnalyticsPoint]
    by_applicant_type: list[AnalyticsPoint]
    by_status: list[AnalyticsPoint]
    daily: list[AnalyticsDay]
    workloads: list[WorkloadItem]
