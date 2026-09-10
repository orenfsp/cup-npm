from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import CreatedAtMixin, UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Security audit metadata only.

    ``metadata_json`` and ``reason`` must never contain appeal or chat text,
    internal notes, crisis contacts, credentials, tokens, raw track numbers,
    or encryption keys. Future write services must enforce an allowlist.
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_actor_created", "actor_staff_user_id", "created_at"),
        Index("ix_audit_log_entity_created", "entity_type", "entity_id", "created_at"),
        Index("ix_audit_log_action_created", "action", "created_at"),
    )

    actor_staff_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[UUID | None]
    reason: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        comment=(
            "Allowlisted non-sensitive audit metadata only; never content, credentials, "
            "raw track numbers, contacts, tokens, or keys."
        ),
    )
