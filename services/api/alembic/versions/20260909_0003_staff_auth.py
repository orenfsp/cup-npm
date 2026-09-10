"""Add revocable staff authentication sessions.

Revision ID: 20260909_0003
Revises: 20260909_0002
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260909_0003"
down_revision: str | None = "20260909_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "staff_sessions",
        sa.Column("staff_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("refresh_token_digest", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotation_counter", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "rotation_counter >= 0",
            name=op.f("ck_staff_sessions_staff_sessions_nonnegative_rotation_counter"),
        ),
        sa.CheckConstraint(
            "octet_length(refresh_token_digest) = 32",
            name=op.f("ck_staff_sessions_staff_sessions_refresh_digest_length"),
        ),
        sa.ForeignKeyConstraint(
            ["staff_user_id"],
            ["staff_users.id"],
            name=op.f("fk_staff_sessions_staff_user_id_staff_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_sessions")),
    )
    op.create_index(
        "ix_staff_sessions_refresh_token_digest",
        "staff_sessions",
        ["refresh_token_digest"],
        unique=True,
    )
    op.create_index(
        "ix_staff_sessions_staff_user_id_expires_at",
        "staff_sessions",
        ["staff_user_id", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_staff_sessions_staff_user_id_expires_at", table_name="staff_sessions")
    op.drop_index("ix_staff_sessions_refresh_token_digest", table_name="staff_sessions")
    op.drop_table("staff_sessions")
