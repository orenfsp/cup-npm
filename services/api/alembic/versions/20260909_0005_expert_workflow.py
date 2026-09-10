"""Add encrypted transfer reasons and applicant return explanations.

Revision ID: 20260909_0005
Revises: 20260909_0004
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260909_0005"
down_revision: str | None = "20260909_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TIMESTAMP = sa.DateTime(timezone=True)


def upgrade() -> None:
    # Phase 4 never exposed transfer creation. Refuse to discard unexpected manual
    # legacy rows because Alembic cannot encrypt them without application key material.
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM transfer_requests) THEN "
        "RAISE EXCEPTION 'Phase 5 migration requires an empty transfer_requests table'; "
        "END IF; END $$"
    )
    op.add_column("transfer_requests", sa.Column("encrypted_reason", sa.LargeBinary()))
    op.add_column("transfer_requests", sa.Column("key_version", sa.SmallInteger()))
    op.alter_column(
        "transfer_requests", "encrypted_reason", existing_type=sa.LargeBinary(), nullable=False
    )
    op.alter_column(
        "transfer_requests", "key_version", existing_type=sa.SmallInteger(), nullable=False
    )
    op.drop_column("transfer_requests", "reason")
    op.create_check_constraint(
        op.f("ck_transfer_requests_transfer_requests_positive_key_version"),
        "transfer_requests",
        "key_version > 0",
    )

    op.create_table(
        "appeal_return_explanations",
        sa.Column("appeal_id", UUID, nullable=False),
        sa.Column("return_number", sa.SmallInteger(), nullable=False),
        sa.Column("encrypted_body", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.SmallInteger(), nullable=False),
        sa.Column("id", UUID, nullable=False),
        sa.Column(
            "created_at", TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint(
            "key_version > 0",
            name=op.f(
                "ck_appeal_return_explanations_appeal_return_explanations_positive_key_version"
            ),
        ),
        sa.CheckConstraint(
            "return_number > 0",
            name=op.f(
                "ck_appeal_return_explanations_appeal_return_explanations_positive_return_number"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["appeal_id"],
            ["appeals.id"],
            name=op.f("fk_appeal_return_explanations_appeal_id_appeals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appeal_return_explanations")),
        sa.UniqueConstraint(
            "appeal_id",
            "return_number",
            name="appeal_return_explanations_appeal_number",
        ),
    )
    op.create_index(
        "ix_appeal_return_explanations_appeal_created",
        "appeal_return_explanations",
        ["appeal_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("appeal_return_explanations")
    op.drop_constraint(
        op.f("ck_transfer_requests_transfer_requests_positive_key_version"),
        "transfer_requests",
        type_="check",
    )
    # A downgrade cannot decrypt text without application key material. Restore the
    # pre-Phase-5 required column with a non-sensitive operational marker.
    op.add_column(
        "transfer_requests",
        sa.Column(
            "reason",
            sa.Text(),
            server_default="[encrypted in removed Phase 5 fields]",
            nullable=False,
        ),
    )
    op.alter_column("transfer_requests", "reason", server_default=None)
    op.drop_column("transfer_requests", "key_version")
    op.drop_column("transfer_requests", "encrypted_reason")
