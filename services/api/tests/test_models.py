import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models.enums import (
    AppealParticipantRole,
    AppealPriority,
    AppealStatus,
    ApplicantType,
    MessageAuthorType,
    RejectionKind,
    StaffRole,
    TransferRequestStatus,
)


def test_phase_2a_defines_expected_tables() -> None:
    assert set(Base.metadata.tables) == {
        "appeal_contents",
        "appeal_feedback",
        "appeal_intake_answers",
        "appeal_messages",
        "appeal_participants",
        "appeal_rejections",
        "appeal_return_explanations",
        "applicant_types",
        "appeals",
        "assignment_history",
        "attachments",
        "audit_log",
        "categories",
        "category_group_rules",
        "category_intake_questions",
        "crisis_contacts",
        "crisis_rules",
        "crisis_support_resources",
        "expert_group_memberships",
        "expert_profiles",
        "internal_notes",
        "intake_questions",
        "specialist_groups",
        "staff_complaints",
        "staff_invitations",
        "staff_sessions",
        "staff_users",
        "status_history",
        "transfer_requests",
    }


def test_domain_enums_use_stable_lowercase_values() -> None:
    enum_classes = (
        ApplicantType,
        StaffRole,
        AppealStatus,
        AppealPriority,
        AppealParticipantRole,
        TransferRequestStatus,
        MessageAuthorType,
        RejectionKind,
    )

    for enum_class in enum_classes:
        assert all(member.value == member.value.lower() for member in enum_class)


def test_models_do_not_expose_applicant_identity_fields() -> None:
    forbidden_columns = {
        "advertising_id",
        "analytics_identifier",
        "applicant_email",
        "applicant_id",
        "applicant_name",
        "applicant_phone",
        "browser_fingerprint",
        "device_fingerprint",
        "email",
        "ip_address",
        "phone",
        "school",
        "user_agent",
    }

    anonymous_domain_tables = {
        "appeals",
        "appeal_contents",
        "appeal_intake_answers",
        "appeal_messages",
        "appeal_feedback",
        "appeal_return_explanations",
        "attachments",
        "crisis_contacts",
        "staff_complaints",
    }
    all_columns = {
        column.name
        for name, table in Base.metadata.tables.items()
        if name in anonymous_domain_tables
        for column in table.columns
    }
    assert forbidden_columns.isdisjoint(all_columns)


def test_appeals_has_only_a_digest_for_track_lookup() -> None:
    appeal_columns = set(Base.metadata.tables["appeals"].columns.keys())

    assert "track_digest" in appeal_columns
    assert {"track_number", "track_code", "plaintext_track"}.isdisjoint(appeal_columns)


def test_crisis_contact_is_separate_from_appeal_metadata() -> None:
    appeal_columns = set(Base.metadata.tables["appeals"].columns.keys())

    assert "encrypted_contact" not in appeal_columns
    assert "encrypted_contact" in Base.metadata.tables["crisis_contacts"].columns


def test_appeal_content_is_separate_from_metadata() -> None:
    appeal_columns = set(Base.metadata.tables["appeals"].columns.keys())

    assert "encrypted_content" not in appeal_columns
    assert "encrypted_content" in Base.metadata.tables["appeal_contents"].columns


def test_attachments_do_not_store_identifying_filenames_or_public_urls() -> None:
    attachment_columns = set(Base.metadata.tables["attachments"].columns.keys())

    assert {"original_filename", "filename", "public_url"}.isdisjoint(attachment_columns)


def test_staff_sessions_store_no_plaintext_token_or_network_identity() -> None:
    session_columns = set(Base.metadata.tables["staff_sessions"].columns.keys())

    assert "refresh_token_digest" in session_columns
    assert {
        "refresh_token",
        "ip",
        "ip_address",
        "user_agent",
        "device_fingerprint",
    }.isdisjoint(session_columns)


def test_no_applicant_account_model_exists() -> None:
    table_names = set(Base.metadata.tables)

    assert {"applicants", "applicant_users", "anonymous_users"}.isdisjoint(table_names)


def test_transfer_and_return_sensitive_text_use_encrypted_columns() -> None:
    transfer_columns = set(Base.metadata.tables["transfer_requests"].columns.keys())
    return_columns = set(Base.metadata.tables["appeal_return_explanations"].columns.keys())

    assert {"encrypted_reason", "key_version"}.issubset(transfer_columns)
    assert "reason" not in transfer_columns
    assert {"encrypted_body", "key_version"}.issubset(return_columns)
    assert "body" not in return_columns
