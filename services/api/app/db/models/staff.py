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
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import StaffRole, string_enum


class StaffUser(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Internal staff identity; anonymous applicants never have user records."""

    __tablename__ = "staff_users"
    __table_args__ = (
        UniqueConstraint("login", name="staff_users_login"),
        CheckConstraint("login = lower(btrim(login))", name="staff_users_login_normalized"),
        CheckConstraint(
            "email IS NULL OR email = lower(btrim(email))",
            name="staff_users_email_normalized",
        ),
        Index("uq_staff_users_email", "email", unique=True),
    )

    login: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(512))
    email: Mapped[str | None] = mapped_column(String(320))
    role: Mapped[StaffRole] = mapped_column(
        string_enum(StaffRole, name="staff_role"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExpertProfile(Base):
    __tablename__ = "expert_profiles"
    __table_args__ = (
        CheckConstraint("max_active_appeals > 0", name="expert_profiles_positive_capacity"),
    )

    staff_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff_users.id", ondelete="CASCADE"), primary_key=True
    )
    max_active_appeals: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10, server_default=text("10")
    )
    public_specialist_label: Mapped[str | None] = mapped_column(String(120))


class ExpertGroupMembership(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "expert_group_memberships"
    __table_args__ = (
        UniqueConstraint("expert_id", "specialist_group_id", name="expert_group_memberships_pair"),
    )

    expert_id: Mapped[UUID] = mapped_column(
        ForeignKey("expert_profiles.staff_user_id", ondelete="CASCADE"), nullable=False
    )
    specialist_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("specialist_groups.id", ondelete="CASCADE"), nullable=False
    )


class StaffSession(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Revocable staff refresh session; raw refresh tokens are never persisted."""

    __tablename__ = "staff_sessions"
    __table_args__ = (
        CheckConstraint(
            "octet_length(refresh_token_digest) = 32",
            name="staff_sessions_refresh_digest_length",
        ),
        CheckConstraint(
            "rotation_counter >= 0", name="staff_sessions_nonnegative_rotation_counter"
        ),
        Index("ix_staff_sessions_refresh_token_digest", "refresh_token_digest", unique=True),
        Index("ix_staff_sessions_staff_user_id_expires_at", "staff_user_id", "expires_at"),
    )

    staff_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff_users.id", ondelete="CASCADE"), nullable=False
    )
    refresh_token_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rotation_counter: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
