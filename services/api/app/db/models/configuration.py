from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import (
    ApplicantTone,
    IntakeFieldType,
    StaffInvitationPurpose,
    string_enum,
)


class StaffInvitation(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One-time staff credential setup; only the token digest is persisted."""

    __tablename__ = "staff_invitations"
    __table_args__ = (
        CheckConstraint(
            "octet_length(token_digest) = 32", name="staff_invitations_token_digest_length"
        ),
        Index("ix_staff_invitations_token_digest", "token_digest", unique=True),
        Index("ix_staff_invitations_staff_expires", "staff_user_id", "expires_at"),
    )

    staff_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff_users.id", ondelete="CASCADE"), nullable=False
    )
    issued_by_staff_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="SET NULL")
    )
    token_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    purpose: Mapped[StaffInvitationPurpose] = mapped_column(
        string_enum(StaffInvitationPurpose, name="staff_invitation_purpose"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApplicantTypeConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "applicant_types"
    __table_args__ = (
        UniqueConstraint("code", name="applicant_types_code"),
        CheckConstraint("code = lower(btrim(code))", name="applicant_types_code_normalized"),
        CheckConstraint("sort_order >= 0", name="applicant_types_nonnegative_sort_order"),
    )

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    tone: Mapped[ApplicantTone] = mapped_column(
        string_enum(ApplicantTone, name="applicant_tone"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )


class IntakeQuestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "intake_questions"
    __table_args__ = (
        UniqueConstraint("code", name="intake_questions_code"),
        CheckConstraint("code = lower(btrim(code))", name="intake_questions_code_normalized"),
        CheckConstraint("sort_order >= 0", name="intake_questions_nonnegative_sort_order"),
        CheckConstraint(
            "jsonb_typeof(options_json) = 'array'", name="intake_questions_options_array"
        ),
    )

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    help_text: Mapped[str | None] = mapped_column(Text)
    field_type: Mapped[IntakeFieldType] = mapped_column(
        string_enum(IntakeFieldType, name="intake_field_type"), nullable=False
    )
    options_json: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )


class CategoryIntakeQuestion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "category_intake_questions"
    __table_args__ = (
        UniqueConstraint("category_id", "question_id", name="category_intake_questions_pair"),
        CheckConstraint("sort_order >= 0", name="category_intake_questions_nonnegative_sort_order"),
    )

    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("intake_questions.id", ondelete="CASCADE"), nullable=False
    )
    required_override: Mapped[bool | None] = mapped_column(Boolean)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )


class CrisisSupportResource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crisis_support_resources"
    __table_args__ = (
        CheckConstraint(
            "phone IS NOT NULL OR url IS NOT NULL",
            name="crisis_support_resources_contact_present",
        ),
        CheckConstraint("sort_order >= 0", name="crisis_support_resources_nonnegative_sort_order"),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(60))
    url: Mapped[str | None] = mapped_column(String(500))
    region: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
