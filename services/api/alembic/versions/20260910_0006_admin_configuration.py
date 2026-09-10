"""Add the Phase 6A administrator configuration schema.

Revision ID: 20260910_0006
Revises: 20260909_0005
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260910_0006"
down_revision: str | None = "20260909_0005"
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


def upgrade() -> None:
    op.add_column("staff_users", sa.Column("email", sa.String(length=320)))
    op.add_column("staff_users", sa.Column("last_login_at", TIMESTAMP))
    op.alter_column(
        "staff_users", "password_hash", existing_type=sa.String(length=512), nullable=True
    )
    op.create_check_constraint(
        op.f("ck_staff_users_staff_users_email_normalized"),
        "staff_users",
        "email IS NULL OR email = lower(btrim(email))",
    )
    op.create_index("uq_staff_users_email", "staff_users", ["email"], unique=True)
    op.add_column("expert_profiles", sa.Column("public_specialist_label", sa.String(length=120)))

    op.create_table(
        "staff_invitations",
        sa.Column("staff_user_id", UUID, nullable=False),
        sa.Column("issued_by_staff_user_id", UUID),
        sa.Column("token_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("expires_at", TIMESTAMP, nullable=False),
        sa.Column("consumed_at", TIMESTAMP),
        sa.Column("id", UUID, nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "octet_length(token_digest) = 32",
            name=op.f("ck_staff_invitations_staff_invitations_token_digest_length"),
        ),
        sa.CheckConstraint(
            "purpose IN ('invitation', 'password_reset')",
            name=op.f("ck_staff_invitations_staff_invitation_purpose"),
        ),
        sa.ForeignKeyConstraint(
            ["issued_by_staff_user_id"],
            ["staff_users.id"],
            name=op.f("fk_staff_invitations_issued_by_staff_user_id_staff_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["staff_user_id"],
            ["staff_users.id"],
            name=op.f("fk_staff_invitations_staff_user_id_staff_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_invitations")),
    )
    op.create_index(
        "ix_staff_invitations_token_digest",
        "staff_invitations",
        ["token_digest"],
        unique=True,
    )
    op.create_index(
        "ix_staff_invitations_staff_expires",
        "staff_invitations",
        ["staff_user_id", "expires_at"],
    )

    op.create_table(
        "applicant_types",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("tone", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("id", UUID, nullable=False),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "code = lower(btrim(code))",
            name=op.f("ck_applicant_types_applicant_types_code_normalized"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_applicant_types_applicant_types_nonnegative_sort_order"),
        ),
        sa.CheckConstraint(
            "tone IN ('informal', 'formal')",
            name=op.f("ck_applicant_types_applicant_tone"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_applicant_types")),
        sa.UniqueConstraint("code", name="applicant_types_code"),
    )
    applicant_types = sa.table(
        "applicant_types",
        sa.column("id", UUID),
        sa.column("code", sa.String),
        sa.column("label", sa.String),
        sa.column("description", sa.Text),
        sa.column("tone", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(
        applicant_types,
        [
            {
                "id": "00000000-0000-0000-0000-000000000101",
                "code": "student",
                "label": "Ученик",
                "description": "Обращение от ученика",
                "tone": "informal",
                "is_active": True,
                "sort_order": 10,
            },
            {
                "id": "00000000-0000-0000-0000-000000000102",
                "code": "parent",
                "label": "Родитель",
                "description": "Обращение от родителя",
                "tone": "formal",
                "is_active": True,
                "sort_order": 20,
            },
            {
                "id": "00000000-0000-0000-0000-000000000103",
                "code": "teacher",
                "label": "Учитель",
                "description": "Обращение от учителя",
                "tone": "formal",
                "is_active": True,
                "sort_order": 30,
            },
        ],
    )
    op.drop_constraint(op.f("ck_appeals_applicant_type"), "appeals", type_="check")
    op.alter_column(
        "appeals",
        "applicant_type",
        existing_type=sa.String(length=32),
        type_=sa.String(length=50),
        existing_nullable=False,
    )
    op.create_foreign_key(
        op.f("fk_appeals_applicant_type_applicant_types"),
        "appeals",
        "applicant_types",
        ["applicant_type"],
        ["code"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "intake_questions",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=300), nullable=False),
        sa.Column("help_text", sa.Text()),
        sa.Column("field_type", sa.String(length=32), nullable=False),
        sa.Column(
            "options_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("required", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("id", UUID, nullable=False),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "code = lower(btrim(code))",
            name=op.f("ck_intake_questions_intake_questions_code_normalized"),
        ),
        sa.CheckConstraint(
            "field_type IN ('short_text', 'long_text', 'single_choice', 'multi_choice', 'boolean')",
            name=op.f("ck_intake_questions_intake_field_type"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_intake_questions_intake_questions_nonnegative_sort_order"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(options_json) = 'array'",
            name=op.f("ck_intake_questions_intake_questions_options_array"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_intake_questions")),
        sa.UniqueConstraint("code", name="intake_questions_code"),
    )
    op.create_table(
        "category_intake_questions",
        sa.Column("category_id", UUID, nullable=False),
        sa.Column("question_id", UUID, nullable=False),
        sa.Column("required_override", sa.Boolean()),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("id", UUID, nullable=False),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f(
                "ck_category_intake_questions_category_intake_questions_nonnegative_sort_order"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_category_intake_questions_category_id_categories"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["intake_questions.id"],
            name=op.f("fk_category_intake_questions_question_id_intake_questions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_category_intake_questions")),
        sa.UniqueConstraint("category_id", "question_id", name="category_intake_questions_pair"),
    )

    op.create_table(
        "crisis_support_resources",
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("phone", sa.String(length=60)),
        sa.Column("url", sa.String(length=500)),
        sa.Column("region", sa.String(length=120)),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("id", UUID, nullable=False),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "phone IS NOT NULL OR url IS NOT NULL",
            name=op.f("ck_crisis_support_resources_crisis_support_resources_contact_present"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f(
                "ck_crisis_support_resources_crisis_support_resources_nonnegative_sort_order"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crisis_support_resources")),
    )


def downgrade() -> None:
    op.drop_table("crisis_support_resources")
    op.drop_table("category_intake_questions")
    op.drop_table("intake_questions")
    op.drop_constraint(
        op.f("fk_appeals_applicant_type_applicant_types"), "appeals", type_="foreignkey"
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM appeals WHERE applicant_type NOT IN "
        "('student', 'parent', 'teacher')) THEN RAISE EXCEPTION "
        "'Cannot downgrade with custom applicant types in use'; END IF; END $$"
    )
    op.alter_column(
        "appeals",
        "applicant_type",
        existing_type=sa.String(length=50),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
    op.create_check_constraint(
        op.f("ck_appeals_applicant_type"),
        "appeals",
        "applicant_type IN ('student', 'parent', 'teacher')",
    )
    op.drop_table("applicant_types")
    op.drop_table("staff_invitations")
    op.drop_column("expert_profiles", "public_specialist_label")
    op.drop_index("uq_staff_users_email", table_name="staff_users")
    op.drop_constraint(
        op.f("ck_staff_users_staff_users_email_normalized"), "staff_users", type_="check"
    )
    op.alter_column(
        "staff_users", "password_hash", existing_type=sa.String(length=512), nullable=False
    )
    op.drop_column("staff_users", "last_login_at")
    op.drop_column("staff_users", "email")
