"""Add persistent crisis rules and encrypted rejection explanations.

Revision ID: 20260909_0004
Revises: 20260909_0003
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260909_0004"
down_revision: str | None = "20260909_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TIMESTAMP = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "crisis_rules",
        sa.Column("phrase", sa.String(length=300), nullable=False),
        sa.Column("normalized_phrase", sa.String(length=300), nullable=False),
        sa.Column("compact_phrase", sa.String(length=300), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "allow_compact_match", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("id", UUID, nullable=False),
        sa.Column(
            "created_at", TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint(
            "compact_phrase = btrim(compact_phrase)",
            name=op.f("ck_crisis_rules_crisis_rules_compact_trimmed"),
        ),
        sa.CheckConstraint(
            "char_length(compact_phrase) > 0",
            name=op.f("ck_crisis_rules_crisis_rules_compact_nonempty"),
        ),
        sa.CheckConstraint(
            "char_length(normalized_phrase) > 0",
            name=op.f("ck_crisis_rules_crisis_rules_normalized_nonempty"),
        ),
        sa.CheckConstraint(
            "normalized_phrase = btrim(normalized_phrase)",
            name=op.f("ck_crisis_rules_crisis_rules_normalized_trimmed"),
        ),
        sa.CheckConstraint(
            "phrase = btrim(phrase)", name=op.f("ck_crisis_rules_crisis_rules_phrase_trimmed")
        ),
        sa.CheckConstraint(
            "sort_order >= 0", name=op.f("ck_crisis_rules_crisis_rules_nonnegative_sort_order")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crisis_rules")),
        sa.UniqueConstraint("normalized_phrase", name="crisis_rules_normalized_phrase"),
    )

    op.create_table(
        "appeal_rejections",
        sa.Column("appeal_id", UUID, nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("encrypted_reason", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at", TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint(
            "key_version > 0",
            name=op.f("ck_appeal_rejections_appeal_rejections_positive_key_version"),
        ),
        sa.CheckConstraint(
            "kind IN ('spam', 'outside_competence')",
            name=op.f("ck_appeal_rejections_rejection_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["appeal_id"],
            ["appeals.id"],
            name=op.f("fk_appeal_rejections_appeal_id_appeals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("appeal_id", name=op.f("pk_appeal_rejections")),
    )


def downgrade() -> None:
    op.drop_table("appeal_rejections")
    op.drop_table("crisis_rules")
