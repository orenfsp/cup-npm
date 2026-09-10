from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

from app.db.models.enums import AppealStatus, ApplicantTone, IntakeFieldType, MessageAuthorType


class CategoryPublic(BaseModel):
    id: UUID
    slug: str
    name: str
    description: str | None
    requires_description: bool


class IntakeQuestionPublic(BaseModel):
    id: str
    prompt_student: str
    prompt_formal: str
    max_length: int
    optional: bool = True
    label: str
    help_text: str | None
    field_type: IntakeFieldType
    options: list[str]
    required: bool
    category_ids: list[UUID]
    required_category_ids: list[UUID]


class ApplicantTypePublic(BaseModel):
    code: str
    label: str
    description: str | None
    tone: ApplicantTone


class CrisisSupportResourcePublic(BaseModel):
    title: str
    message: str
    phone: str | None = None
    url: str | None = None
    requires_organizer_verification: bool


class PublicReferenceResponse(BaseModel):
    applicant_types: list[ApplicantTypePublic]
    categories: list[CategoryPublic]
    intake_questions: list[IntakeQuestionPublic]
    crisis_support_resources: list[CrisisSupportResourcePublic]


class AppealCreateRequest(BaseModel):
    applicant_type: str = Field(min_length=2, max_length=50, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    category_id: UUID | None = None
    description: SecretStr | None = Field(default=None, max_length=5000)
    intake_answers: dict[str, SecretStr | bool | list[SecretStr]] | None = Field(
        default=None, max_length=100
    )

    @field_validator("intake_answers")
    @classmethod
    def validate_intake_answers(
        cls, value: dict[str, SecretStr | bool | list[SecretStr]] | None
    ) -> dict[str, SecretStr | bool | list[SecretStr]] | None:
        if value is None:
            return None
        for answer in value.values():
            values = answer if isinstance(answer, list) else [answer]
            if len(values) > 30:
                raise ValueError("Too many selected answers")
            if any(
                isinstance(item, SecretStr) and len(item.get_secret_value()) > 2000
                for item in values
            ):
                raise ValueError("Intake answers must not exceed 2000 characters")
        return value

    @model_validator(mode="after")
    def require_category_or_description(self) -> Self:
        description = self.description.get_secret_value().strip() if self.description else ""
        if self.category_id is None and not description:
            raise ValueError("Choose a category or describe the situation")
        return self


class StatusTimelineItem(BaseModel):
    status: AppealStatus
    text: str
    occurred_at: datetime


class AppealCreatedResponse(BaseModel):
    track_number: str
    status: AppealStatus
    status_text: str
    crisis_flag: bool
    show_crisis_support: bool
    crisis_support_resources: list[CrisisSupportResourcePublic]


class AppealAccessRequest(BaseModel):
    track_number: SecretStr = Field(min_length=1, max_length=40)


class AppealAccessResponse(BaseModel):
    status: str = "ok"


class CurrentAppealResponse(BaseModel):
    applicant_type: str
    category: CategoryPublic | None
    status: AppealStatus
    status_text: str
    crisis_flag: bool
    show_crisis_support: bool
    crisis_support_resources: list[CrisisSupportResourcePublic]
    created_at: datetime
    updated_at: datetime
    timeline: list[StatusTimelineItem]
    rejection_reason: str | None = None
    return_count: int
    max_returns: int


class PublicMessage(BaseModel):
    id: UUID
    author_type: MessageAuthorType
    author_label: str
    body: str
    created_at: datetime


class PublicMessagesResponse(BaseModel):
    messages: list[PublicMessage]


class PublicMessageRequest(BaseModel):
    body: SecretStr = Field(min_length=1, max_length=5000)


class ResolveAppealRequest(BaseModel):
    choice: Literal["helped", "not_helped"]
    explanation: SecretStr | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_return_explanation(self) -> Self:
        if self.choice == "not_helped":
            value = self.explanation.get_secret_value().strip() if self.explanation else ""
            if not value:
                raise ValueError("Please explain what was missing")
        return self


class FeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: SecretStr | None = Field(default=None, max_length=2000)


class ComplaintRequest(BaseModel):
    body: SecretStr = Field(min_length=1, max_length=3000)


class CrisisContactRequest(BaseModel):
    contact: SecretStr = Field(min_length=1, max_length=1000)


class SavedResponse(BaseModel):
    status: str = "saved"


class AttachmentResponse(BaseModel):
    status: str = "stored"
    mime_type: str
    byte_size: int


class LeaveResponse(BaseModel):
    status: str = "left"
