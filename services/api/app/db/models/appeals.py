from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import (
    AppealParticipantRole,
    AppealPriority,
    AppealStatus,
    MessageAuthorType,
    RejectionKind,
    TransferRequestStatus,
    string_enum,
)


class Appeal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Operational appeal metadata only; content and identity data do not belong here."""

    __tablename__ = "appeals"
    __table_args__ = (
        CheckConstraint(
            "suggested_category_score IS NULL OR "
            "(suggested_category_score >= 0 AND suggested_category_score <= 1)",
            name="appeals_suggested_score_range",
        ),
        CheckConstraint("return_count >= 0", name="appeals_nonnegative_return_count"),
        CheckConstraint("octet_length(track_digest) = 32", name="appeals_track_digest_length"),
        Index("ix_appeals_track_digest", "track_digest", unique=True),
        Index("ix_appeals_status_created_at", "status", "created_at"),
        Index("ix_appeals_assigned_expert_status", "assigned_expert_id", "status"),
    )

    track_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    applicant_type: Mapped[str] = mapped_column(
        String(50), ForeignKey("applicant_types.code", ondelete="RESTRICT"), nullable=False
    )
    category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL")
    )
    suggested_category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL")
    )
    suggested_category_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    status: Mapped[AppealStatus] = mapped_column(
        string_enum(AppealStatus, name="appeal_status"),
        nullable=False,
        default=AppealStatus.NEW,
        server_default=text("'new'"),
    )
    priority: Mapped[AppealPriority] = mapped_column(
        string_enum(AppealPriority, name="appeal_priority"),
        nullable=False,
        default=AppealPriority.STANDARD,
        server_default=text("'standard'"),
    )
    crisis_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    assigned_expert_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("expert_profiles.staff_user_id", ondelete="SET NULL")
    )
    operator_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_specialist_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answer_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    return_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )


class AppealContent(TimestampMixin, Base):
    __tablename__ = "appeal_contents"
    __table_args__ = (
        CheckConstraint("key_version > 0", name="appeal_contents_positive_key_version"),
    )

    appeal_id: Mapped[UUID] = mapped_column(
        ForeignKey("appeals.id", ondelete="CASCADE"), primary_key=True
    )
    encrypted_content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class AppealIntakeAnswer(TimestampMixin, Base):
    __tablename__ = "appeal_intake_answers"
    __table_args__ = (
        CheckConstraint("key_version > 0", name="appeal_intake_answers_positive_key_version"),
    )

    appeal_id: Mapped[UUID] = mapped_column(
        ForeignKey("appeals.id", ondelete="CASCADE"), primary_key=True
    )
    encrypted_payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class AppealRejection(TimestampMixin, Base):
    """Encrypted applicant-visible rejection explanation, separate from audit data."""

    __tablename__ = "appeal_rejections"
    __table_args__ = (
        CheckConstraint("key_version > 0", name="appeal_rejections_positive_key_version"),
    )

    appeal_id: Mapped[UUID] = mapped_column(
        ForeignKey("appeals.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[RejectionKind] = mapped_column(
        string_enum(RejectionKind, name="rejection_kind"), nullable=False
    )
    encrypted_reason: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class AppealMessage(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "appeal_messages"
    __table_args__ = (
        CheckConstraint(
            "(author_type = 'applicant' AND author_staff_user_id IS NULL) OR "
            "(author_type = 'specialist' AND author_staff_user_id IS NOT NULL)",
            name="appeal_messages_author_consistency",
        ),
        CheckConstraint("key_version > 0", name="appeal_messages_positive_key_version"),
        Index("ix_appeal_messages_appeal_created_at", "appeal_id", "created_at"),
    )

    appeal_id: Mapped[UUID] = mapped_column(
        ForeignKey("appeals.id", ondelete="CASCADE"), nullable=False
    )
    author_type: Mapped[MessageAuthorType] = mapped_column(
        string_enum(MessageAuthorType, name="message_author_type"), nullable=False
    )
    author_staff_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="RESTRICT")
    )
    encrypted_body: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class InternalNote(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "internal_notes"
    __table_args__ = (
        CheckConstraint("key_version > 0", name="internal_notes_positive_key_version"),
        Index("ix_internal_notes_appeal_created_at", "appeal_id", "created_at"),
    )

    appeal_id: Mapped[UUID] = mapped_column(
        ForeignKey("appeals.id", ondelete="CASCADE"), nullable=False
    )
    author_staff_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff_users.id", ondelete="RESTRICT"), nullable=False
    )
    encrypted_body: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class CrisisContact(TimestampMixin, Base):
    """Encrypted crisis contact isolated behind dedicated operator authorization."""

    __tablename__ = "crisis_contacts"
    __table_args__ = (
        CheckConstraint("key_version > 0", name="crisis_contacts_positive_key_version"),
    )

    appeal_id: Mapped[UUID] = mapped_column(
        ForeignKey("appeals.id", ondelete="CASCADE"), primary_key=True
    )
    encrypted_contact: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class AppealParticipant(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "appeal_participants"
    __table_args__ = (
        CheckConstraint(
            "NOT is_active OR left_at IS NULL",
            name="appeal_participants_active_has_no_left_at",
        ),
        Index(
            "uq_appeal_participants_active_staff",
            "appeal_id",
            "staff_user_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index(
            "uq_appeal_participants_current_primary",
            "appeal_id",
            unique=True,
            postgresql_where=text("is_active AND participant_role = 'primary'"),
        ),
    )

    appeal_id: Mapped[UUID] = mapped_column(
        ForeignKey("appeals.id", ondelete="CASCADE"), nullable=False
    )
    staff_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff_users.id", ondelete="RESTRICT"), nullable=False
    )
    participant_role: Mapped[AppealParticipantRole] = mapped_column(
        string_enum(AppealParticipantRole, name="appeal_participant_role"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AssignmentHistory(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "assignment_history"
    __table_args__ = (Index("ix_assignment_history_appeal_created", "appeal_id", "created_at"),)

    appeal_id: Mapped[UUID] = mapped_column(
        ForeignKey("appeals.id", ondelete="CASCADE"), nullable=False
    )
    from_expert_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("expert_profiles.staff_user_id", ondelete="SET NULL")
    )
    to_expert_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("expert_profiles.staff_user_id", ondelete="SET NULL")
    )
    changed_by_staff_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff_users.id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text)


class StatusHistory(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "status_history"
    __table_args__ = (Index("ix_status_history_appeal_created", "appeal_id", "created_at"),)

    appeal_id: Mapped[UUID] = mapped_column(
        ForeignKey("appeals.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[AppealStatus | None] = mapped_column(
        string_enum(AppealStatus, name="status_history_from_status")
    )
    to_status: Mapped[AppealStatus] = mapped_column(
        string_enum(AppealStatus, name="status_history_to_status"), nullable=False
    )
    changed_by_staff_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="SET NULL")
    )
    reason: Mapped[str | None] = mapped_column(Text)


class TransferRequest(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "transfer_requests"
    __table_args__ = (
        CheckConstraint(
            "(status = 'pending' AND resolved_at IS NULL AND resolved_by_staff_user_id IS NULL) "
            "OR (status IN ('approved', 'rejected') AND resolved_at IS NOT NULL)",
            name="transfer_requests_resolution_consistency",
        ),
        CheckConstraint("key_version > 0", name="transfer_requests_positive_key_version"),
        Index("ix_transfer_requests_appeal_status", "appeal_id", "status"),
    )

    appeal_id: Mapped[UUID] = mapped_column(
        ForeignKey("appeals.id", ondelete="CASCADE"), nullable=False
    )
    requested_by_staff_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff_users.id", ondelete="RESTRICT"), nullable=False
    )
    requested_target_staff_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="SET NULL")
    )
    encrypted_reason: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[TransferRequestStatus] = mapped_column(
        string_enum(TransferRequestStatus, name="transfer_request_status"),
        nullable=False,
        default=TransferRequestStatus.PENDING,
        server_default=text("'pending'"),
    )
    resolved_by_staff_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AppealReturnExplanation(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Encrypted applicant explanation for a bounded return to operator triage."""

    __tablename__ = "appeal_return_explanations"
    __table_args__ = (
        UniqueConstraint(
            "appeal_id", "return_number", name="appeal_return_explanations_appeal_number"
        ),
        CheckConstraint(
            "return_number > 0", name="appeal_return_explanations_positive_return_number"
        ),
        CheckConstraint("key_version > 0", name="appeal_return_explanations_positive_key_version"),
        Index(
            "ix_appeal_return_explanations_appeal_created",
            "appeal_id",
            "created_at",
        ),
    )

    appeal_id: Mapped[UUID] = mapped_column(
        ForeignKey("appeals.id", ondelete="CASCADE"), nullable=False
    )
    return_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    encrypted_body: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class AppealFeedback(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "appeal_feedback"
    __table_args__ = (
        CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)",
            name="appeal_feedback_rating_range",
        ),
        CheckConstraint(
            "(encrypted_comment IS NULL AND key_version IS NULL) OR "
            "(encrypted_comment IS NOT NULL AND key_version IS NOT NULL AND key_version > 0)",
            name="appeal_feedback_comment_key_consistency",
        ),
    )

    appeal_id: Mapped[UUID] = mapped_column(
        ForeignKey("appeals.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    encrypted_comment: Mapped[bytes | None] = mapped_column(LargeBinary)
    key_version: Mapped[int | None] = mapped_column(SmallInteger)


class StaffComplaint(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "staff_complaints"
    __table_args__ = (
        CheckConstraint("key_version > 0", name="staff_complaints_positive_key_version"),
        Index("ix_staff_complaints_appeal_created", "appeal_id", "created_at"),
    )

    appeal_id: Mapped[UUID] = mapped_column(
        ForeignKey("appeals.id", ondelete="CASCADE"), nullable=False
    )
    encrypted_body: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Attachment(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Opaque storage metadata; original filenames and public URLs are forbidden."""

    __tablename__ = "attachments"
    __table_args__ = (
        CheckConstraint("byte_size >= 0", name="attachments_nonnegative_byte_size"),
        CheckConstraint(
            "octet_length(sha256_digest) = 32", name="attachments_sha256_digest_length"
        ),
        Index("ix_attachments_appeal_created", "appeal_id", "created_at"),
        Index("uq_attachments_storage_key", "storage_key", unique=True),
    )

    appeal_id: Mapped[UUID] = mapped_column(
        ForeignKey("appeals.id", ondelete="CASCADE"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
