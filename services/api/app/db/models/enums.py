from enum import StrEnum

from sqlalchemy import Enum as SQLAlchemyEnum


class ApplicantType(StrEnum):
    STUDENT = "student"
    PARENT = "parent"
    TEACHER = "teacher"


class ApplicantTone(StrEnum):
    INFORMAL = "informal"
    FORMAL = "formal"


class IntakeFieldType(StrEnum):
    SHORT_TEXT = "short_text"
    LONG_TEXT = "long_text"
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    BOOLEAN = "boolean"


class StaffInvitationPurpose(StrEnum):
    INVITATION = "invitation"
    PASSWORD_RESET = "password_reset"


class StaffRole(StrEnum):
    OPERATOR = "operator"
    EXPERT = "expert"
    ADMIN = "admin"


class AppealStatus(StrEnum):
    NEW = "new"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    NEEDS_CLARIFICATION = "needs_clarification"
    ANSWER_READY = "answer_ready"
    RETURNED = "returned"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CLOSED_NO_RESPONSE = "closed_no_response"


class AppealPriority(StrEnum):
    LOW = "low"
    STANDARD = "standard"
    URGENT = "urgent"


class AppealParticipantRole(StrEnum):
    PRIMARY = "primary"
    COEXECUTOR = "coexecutor"


class TransferRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MessageAuthorType(StrEnum):
    APPLICANT = "applicant"
    SPECIALIST = "specialist"


class RejectionKind(StrEnum):
    SPAM = "spam"
    OUTSIDE_COMPETENCE = "outside_competence"


def string_enum(enum_class: type[StrEnum], *, name: str) -> SQLAlchemyEnum:
    """Build a portable VARCHAR-backed enum with stable lowercase values."""

    return SQLAlchemyEnum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
        length=32,
    )
