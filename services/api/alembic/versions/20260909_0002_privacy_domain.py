"""Add the Phase 2A privacy domain schema.

Revision ID: 20260909_0002
Revises: 20260909_0001
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260909_0002"
down_revision: str | None = "20260909_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TIMESTAMP = sa.DateTime(timezone=True)


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", TIMESTAMP, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
    )


def _updated_at() -> sa.Column:
    return sa.Column(
        "updated_at", TIMESTAMP, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
    )


def _uuid_id() -> sa.Column:
    return sa.Column("id", UUID, nullable=False)


def upgrade() -> None:
    op.create_table(
        "staff_users",
        _uuid_id(),
        sa.Column("login", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "login = lower(btrim(login))",
            name=op.f("ck_staff_users_staff_users_login_normalized"),
        ),
        sa.CheckConstraint(
            "role IN ('operator', 'expert', 'admin')", name=op.f("ck_staff_users_staff_role")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_users")),
        sa.UniqueConstraint("login", name="staff_users_login"),
    )

    op.create_table(
        "categories",
        _uuid_id(),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "sort_order >= 0", name=op.f("ck_categories_categories_nonnegative_sort_order")
        ),
        sa.CheckConstraint(
            "slug = lower(btrim(slug))",
            name=op.f("ck_categories_categories_slug_normalized"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("slug", name="categories_slug"),
    )

    op.create_table(
        "specialist_groups",
        _uuid_id(),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint(
            "slug = lower(btrim(slug))",
            name=op.f("ck_specialist_groups_specialist_groups_slug_normalized"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_specialist_groups")),
        sa.UniqueConstraint("slug", name="specialist_groups_slug"),
    )

    op.create_table(
        "expert_profiles",
        sa.Column("staff_user_id", UUID, nullable=False),
        sa.Column("max_active_appeals", sa.Integer(), server_default=sa.text("10"), nullable=False),
        sa.CheckConstraint(
            "max_active_appeals > 0",
            name=op.f("ck_expert_profiles_expert_profiles_positive_capacity"),
        ),
        sa.ForeignKeyConstraint(
            ["staff_user_id"],
            ["staff_users.id"],
            name=op.f("fk_expert_profiles_staff_user_id_staff_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("staff_user_id", name=op.f("pk_expert_profiles")),
    )

    op.create_table(
        "category_group_rules",
        _uuid_id(),
        sa.Column("category_id", UUID, nullable=False),
        sa.Column("specialist_group_id", UUID, nullable=False),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_category_group_rules_category_id_categories"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["specialist_group_id"],
            ["specialist_groups.id"],
            name=op.f("fk_category_group_rules_specialist_group_id_specialist_groups"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_category_group_rules")),
        sa.UniqueConstraint("category_id", "specialist_group_id", name="category_group_rules_pair"),
    )

    op.create_table(
        "expert_group_memberships",
        _uuid_id(),
        sa.Column("expert_id", UUID, nullable=False),
        sa.Column("specialist_group_id", UUID, nullable=False),
        sa.ForeignKeyConstraint(
            ["expert_id"],
            ["expert_profiles.staff_user_id"],
            name=op.f("fk_expert_group_memberships_expert_id_expert_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["specialist_group_id"],
            ["specialist_groups.id"],
            name=op.f("fk_expert_group_memberships_specialist_group_id_specialist_groups"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expert_group_memberships")),
        sa.UniqueConstraint(
            "expert_id", "specialist_group_id", name="expert_group_memberships_pair"
        ),
    )

    op.create_table(
        "appeals",
        _uuid_id(),
        sa.Column("track_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column("applicant_type", sa.String(length=32), nullable=False),
        sa.Column("category_id", UUID, nullable=True),
        sa.Column("suggested_category_id", UUID, nullable=True),
        sa.Column("suggested_category_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="new", nullable=False),
        sa.Column("priority", sa.String(length=32), server_default="standard", nullable=False),
        sa.Column("crisis_flag", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("assigned_expert_id", UUID, nullable=True),
        sa.Column("operator_accepted_at", TIMESTAMP, nullable=True),
        sa.Column("first_specialist_response_at", TIMESTAMP, nullable=True),
        sa.Column("answer_ready_at", TIMESTAMP, nullable=True),
        sa.Column("completed_at", TIMESTAMP, nullable=True),
        sa.Column("return_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "applicant_type IN ('student', 'parent', 'teacher')",
            name=op.f("ck_appeals_applicant_type"),
        ),
        sa.CheckConstraint(
            "status IN ('new', 'assigned', 'in_progress', 'needs_clarification', "
            "'answer_ready', 'returned', 'completed', 'rejected', 'closed_no_response')",
            name=op.f("ck_appeals_appeal_status"),
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'standard', 'urgent')",
            name=op.f("ck_appeals_appeal_priority"),
        ),
        sa.CheckConstraint(
            "return_count >= 0", name=op.f("ck_appeals_appeals_nonnegative_return_count")
        ),
        sa.CheckConstraint(
            "octet_length(track_digest) = 32",
            name=op.f("ck_appeals_appeals_track_digest_length"),
        ),
        sa.CheckConstraint(
            "suggested_category_score IS NULL OR "
            "(suggested_category_score >= 0 AND suggested_category_score <= 1)",
            name=op.f("ck_appeals_appeals_suggested_score_range"),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_expert_id"],
            ["expert_profiles.staff_user_id"],
            name=op.f("fk_appeals_assigned_expert_id_expert_profiles"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_appeals_category_id_categories"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["suggested_category_id"],
            ["categories.id"],
            name=op.f("fk_appeals_suggested_category_id_categories"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appeals")),
    )
    op.create_index("ix_appeals_track_digest", "appeals", ["track_digest"], unique=True)
    op.create_index(
        "ix_appeals_status_created_at", "appeals", ["status", "created_at"], unique=False
    )
    op.create_index(
        "ix_appeals_assigned_expert_status",
        "appeals",
        ["assigned_expert_id", "status"],
        unique=False,
    )

    op.create_table(
        "appeal_contents",
        sa.Column("appeal_id", UUID, nullable=False),
        sa.Column("encrypted_content", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.SmallInteger(), nullable=False),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "key_version > 0",
            name=op.f("ck_appeal_contents_appeal_contents_positive_key_version"),
        ),
        sa.ForeignKeyConstraint(
            ["appeal_id"],
            ["appeals.id"],
            name=op.f("fk_appeal_contents_appeal_id_appeals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("appeal_id", name=op.f("pk_appeal_contents")),
    )

    op.create_table(
        "appeal_intake_answers",
        sa.Column("appeal_id", UUID, nullable=False),
        sa.Column("encrypted_payload", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.SmallInteger(), nullable=False),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "key_version > 0",
            name=op.f("ck_appeal_intake_answers_appeal_intake_answers_positive_key_version"),
        ),
        sa.ForeignKeyConstraint(
            ["appeal_id"],
            ["appeals.id"],
            name=op.f("fk_appeal_intake_answers_appeal_id_appeals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("appeal_id", name=op.f("pk_appeal_intake_answers")),
    )

    op.create_table(
        "appeal_messages",
        _uuid_id(),
        sa.Column("appeal_id", UUID, nullable=False),
        sa.Column("author_type", sa.String(length=32), nullable=False),
        sa.Column("author_staff_user_id", UUID, nullable=True),
        sa.Column("encrypted_body", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.SmallInteger(), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "author_type IN ('applicant', 'specialist')",
            name=op.f("ck_appeal_messages_message_author_type"),
        ),
        sa.CheckConstraint(
            "(author_type = 'applicant' AND author_staff_user_id IS NULL) OR "
            "(author_type = 'specialist' AND author_staff_user_id IS NOT NULL)",
            name=op.f("ck_appeal_messages_appeal_messages_author_consistency"),
        ),
        sa.CheckConstraint(
            "key_version > 0",
            name=op.f("ck_appeal_messages_appeal_messages_positive_key_version"),
        ),
        sa.ForeignKeyConstraint(
            ["appeal_id"],
            ["appeals.id"],
            name=op.f("fk_appeal_messages_appeal_id_appeals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_staff_user_id"],
            ["staff_users.id"],
            name=op.f("fk_appeal_messages_author_staff_user_id_staff_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appeal_messages")),
    )
    op.create_index(
        "ix_appeal_messages_appeal_created_at",
        "appeal_messages",
        ["appeal_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "internal_notes",
        _uuid_id(),
        sa.Column("appeal_id", UUID, nullable=False),
        sa.Column("author_staff_user_id", UUID, nullable=False),
        sa.Column("encrypted_body", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.SmallInteger(), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "key_version > 0",
            name=op.f("ck_internal_notes_internal_notes_positive_key_version"),
        ),
        sa.ForeignKeyConstraint(
            ["appeal_id"],
            ["appeals.id"],
            name=op.f("fk_internal_notes_appeal_id_appeals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_staff_user_id"],
            ["staff_users.id"],
            name=op.f("fk_internal_notes_author_staff_user_id_staff_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_internal_notes")),
    )
    op.create_index(
        "ix_internal_notes_appeal_created_at",
        "internal_notes",
        ["appeal_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "crisis_contacts",
        sa.Column("appeal_id", UUID, nullable=False),
        sa.Column("encrypted_contact", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.SmallInteger(), nullable=False),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "key_version > 0",
            name=op.f("ck_crisis_contacts_crisis_contacts_positive_key_version"),
        ),
        sa.ForeignKeyConstraint(
            ["appeal_id"],
            ["appeals.id"],
            name=op.f("fk_crisis_contacts_appeal_id_appeals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("appeal_id", name=op.f("pk_crisis_contacts")),
    )

    op.create_table(
        "appeal_participants",
        _uuid_id(),
        sa.Column("appeal_id", UUID, nullable=False),
        sa.Column("staff_user_id", UUID, nullable=False),
        sa.Column("participant_role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "joined_at",
            TIMESTAMP,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("left_at", TIMESTAMP, nullable=True),
        sa.CheckConstraint(
            "participant_role IN ('primary', 'coexecutor')",
            name=op.f("ck_appeal_participants_appeal_participant_role"),
        ),
        sa.CheckConstraint(
            "NOT is_active OR left_at IS NULL",
            name=op.f("ck_appeal_participants_appeal_participants_active_has_no_left_at"),
        ),
        sa.ForeignKeyConstraint(
            ["appeal_id"],
            ["appeals.id"],
            name=op.f("fk_appeal_participants_appeal_id_appeals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["staff_user_id"],
            ["staff_users.id"],
            name=op.f("fk_appeal_participants_staff_user_id_staff_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appeal_participants")),
    )
    op.create_index(
        "uq_appeal_participants_active_staff",
        "appeal_participants",
        ["appeal_id", "staff_user_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "uq_appeal_participants_current_primary",
        "appeal_participants",
        ["appeal_id"],
        unique=True,
        postgresql_where=sa.text("is_active AND participant_role = 'primary'"),
    )

    op.create_table(
        "assignment_history",
        _uuid_id(),
        sa.Column("appeal_id", UUID, nullable=False),
        sa.Column("from_expert_id", UUID, nullable=True),
        sa.Column("to_expert_id", UUID, nullable=True),
        sa.Column("changed_by_staff_user_id", UUID, nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["appeal_id"],
            ["appeals.id"],
            name=op.f("fk_assignment_history_appeal_id_appeals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_staff_user_id"],
            ["staff_users.id"],
            name=op.f("fk_assignment_history_changed_by_staff_user_id_staff_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["from_expert_id"],
            ["expert_profiles.staff_user_id"],
            name=op.f("fk_assignment_history_from_expert_id_expert_profiles"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["to_expert_id"],
            ["expert_profiles.staff_user_id"],
            name=op.f("fk_assignment_history_to_expert_id_expert_profiles"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assignment_history")),
    )
    op.create_index(
        "ix_assignment_history_appeal_created",
        "assignment_history",
        ["appeal_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "status_history",
        _uuid_id(),
        sa.Column("appeal_id", UUID, nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("changed_by_staff_user_id", UUID, nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status IN ('new', 'assigned', 'in_progress', "
            "'needs_clarification', 'answer_ready', 'returned', 'completed', 'rejected', "
            "'closed_no_response')",
            name=op.f("ck_status_history_status_history_from_status"),
        ),
        sa.CheckConstraint(
            "to_status IN ('new', 'assigned', 'in_progress', 'needs_clarification', "
            "'answer_ready', 'returned', 'completed', 'rejected', 'closed_no_response')",
            name=op.f("ck_status_history_status_history_to_status"),
        ),
        sa.ForeignKeyConstraint(
            ["appeal_id"],
            ["appeals.id"],
            name=op.f("fk_status_history_appeal_id_appeals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_staff_user_id"],
            ["staff_users.id"],
            name=op.f("fk_status_history_changed_by_staff_user_id_staff_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_status_history")),
    )
    op.create_index(
        "ix_status_history_appeal_created",
        "status_history",
        ["appeal_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "transfer_requests",
        _uuid_id(),
        sa.Column("appeal_id", UUID, nullable=False),
        sa.Column("requested_by_staff_user_id", UUID, nullable=False),
        sa.Column("requested_target_staff_user_id", UUID, nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("resolved_by_staff_user_id", UUID, nullable=True),
        _created_at(),
        sa.Column("resolved_at", TIMESTAMP, nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name=op.f("ck_transfer_requests_transfer_request_status"),
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND resolved_at IS NULL AND resolved_by_staff_user_id IS NULL) "
            "OR (status IN ('approved', 'rejected') AND resolved_at IS NOT NULL)",
            name=op.f("ck_transfer_requests_transfer_requests_resolution_consistency"),
        ),
        sa.ForeignKeyConstraint(
            ["appeal_id"],
            ["appeals.id"],
            name=op.f("fk_transfer_requests_appeal_id_appeals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_staff_user_id"],
            ["staff_users.id"],
            name=op.f("fk_transfer_requests_requested_by_staff_user_id_staff_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_target_staff_user_id"],
            ["staff_users.id"],
            name=op.f("fk_transfer_requests_requested_target_staff_user_id_staff_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_staff_user_id"],
            ["staff_users.id"],
            name=op.f("fk_transfer_requests_resolved_by_staff_user_id_staff_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transfer_requests")),
    )
    op.create_index(
        "ix_transfer_requests_appeal_status",
        "transfer_requests",
        ["appeal_id", "status"],
        unique=False,
    )

    op.create_table(
        "appeal_feedback",
        _uuid_id(),
        sa.Column("appeal_id", UUID, nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=True),
        sa.Column("encrypted_comment", sa.LargeBinary(), nullable=True),
        sa.Column("key_version", sa.SmallInteger(), nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)",
            name=op.f("ck_appeal_feedback_appeal_feedback_rating_range"),
        ),
        sa.CheckConstraint(
            "(encrypted_comment IS NULL AND key_version IS NULL) OR "
            "(encrypted_comment IS NOT NULL AND key_version IS NOT NULL AND key_version > 0)",
            name=op.f("ck_appeal_feedback_appeal_feedback_comment_key_consistency"),
        ),
        sa.ForeignKeyConstraint(
            ["appeal_id"],
            ["appeals.id"],
            name=op.f("fk_appeal_feedback_appeal_id_appeals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appeal_feedback")),
    )

    op.create_table(
        "staff_complaints",
        _uuid_id(),
        sa.Column("appeal_id", UUID, nullable=False),
        sa.Column("encrypted_body", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.SmallInteger(), nullable=False),
        _created_at(),
        sa.Column("resolved_at", TIMESTAMP, nullable=True),
        sa.CheckConstraint(
            "key_version > 0",
            name=op.f("ck_staff_complaints_staff_complaints_positive_key_version"),
        ),
        sa.ForeignKeyConstraint(
            ["appeal_id"],
            ["appeals.id"],
            name=op.f("fk_staff_complaints_appeal_id_appeals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_complaints")),
    )
    op.create_index(
        "ix_staff_complaints_appeal_created",
        "staff_complaints",
        ["appeal_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "attachments",
        _uuid_id(),
        sa.Column("appeal_id", UUID, nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256_digest", sa.LargeBinary(length=32), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "byte_size >= 0", name=op.f("ck_attachments_attachments_nonnegative_byte_size")
        ),
        sa.CheckConstraint(
            "octet_length(sha256_digest) = 32",
            name=op.f("ck_attachments_attachments_sha256_digest_length"),
        ),
        sa.ForeignKeyConstraint(
            ["appeal_id"],
            ["appeals.id"],
            name=op.f("fk_attachments_appeal_id_appeals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attachments")),
    )
    op.create_index(
        "ix_attachments_appeal_created",
        "attachments",
        ["appeal_id", "created_at"],
        unique=False,
    )
    op.create_index("uq_attachments_storage_key", "attachments", ["storage_key"], unique=True)

    op.create_table(
        "audit_log",
        _uuid_id(),
        sa.Column("actor_staff_user_id", UUID, nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", UUID, nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "Allowlisted non-sensitive audit metadata only; never content, credentials, "
                "raw track numbers, contacts, tokens, or keys."
            ),
        ),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["actor_staff_user_id"],
            ["staff_users.id"],
            name=op.f("fk_audit_log_actor_staff_user_id_staff_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index(
        "ix_audit_log_actor_created",
        "audit_log",
        ["actor_staff_user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_log_entity_created",
        "audit_log",
        ["entity_type", "entity_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_log_action_created",
        "audit_log",
        ["action", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("attachments")
    op.drop_table("staff_complaints")
    op.drop_table("appeal_feedback")
    op.drop_table("transfer_requests")
    op.drop_table("status_history")
    op.drop_table("assignment_history")
    op.drop_table("appeal_participants")
    op.drop_table("crisis_contacts")
    op.drop_table("internal_notes")
    op.drop_table("appeal_messages")
    op.drop_table("appeal_intake_answers")
    op.drop_table("appeal_contents")
    op.drop_table("appeals")
    op.drop_table("expert_group_memberships")
    op.drop_table("category_group_rules")
    op.drop_table("expert_profiles")
    op.drop_table("specialist_groups")
    op.drop_table("categories")
    op.drop_table("staff_users")
