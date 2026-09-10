from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool
from sqlalchemy.sql import Executable

from alembic import command
from app.core.config import Settings
from app.db.models import (
    Appeal,
    AppealFeedback,
    AppealMessage,
    AppealParticipant,
    AppealReturnExplanation,
    ApplicantType,
    CrisisRule,
    MessageAuthorType,
    StaffRole,
    StaffSession,
    StaffUser,
    TransferRequest,
)

API_ROOT = Path(__file__).resolve().parents[2]
CURRENT_REVISION = "20260910_0007"


def _run_upgrade(connection: Connection) -> None:
    alembic_config = Config(API_ROOT / "alembic.ini")
    alembic_config.attributes["connection"] = connection
    command.upgrade(alembic_config, "head")


@pytest.fixture(scope="session")
def migrated_database_engine() -> Iterator[Engine]:
    async_url = make_url(Settings().database_url)
    sync_url = async_url.set(drivername="postgresql+psycopg")
    engine = create_engine(sync_url, poolclass=NullPool, connect_args={"connect_timeout": 3})
    with engine.connect() as connection:
        _run_upgrade(connection)
    yield engine
    engine.dispose()


def _expect_integrity_error(connection: Connection, statement: Executable) -> None:
    savepoint = connection.begin_nested()
    try:
        with pytest.raises(IntegrityError):
            connection.execute(statement)
    finally:
        savepoint.rollback()


def _insert_appeal(connection: Connection, *, digest: bytes = b"t" * 32) -> UUID:
    appeal_id = uuid4()
    connection.execute(
        Appeal.__table__.insert().values(
            id=appeal_id,
            track_digest=digest,
            applicant_type=ApplicantType.STUDENT,
        )
    )
    return appeal_id


def _insert_staff(connection: Connection) -> UUID:
    staff_id = uuid4()
    connection.execute(
        StaffUser.__table__.insert().values(
            id=staff_id,
            login=f"expert-{staff_id}",
            password_hash="unused-phase-2a-hash",
            role=StaffRole.EXPERT,
            display_name="Integration Expert",
        )
    )
    return staff_id


def test_alembic_upgrade_reaches_current_revision(
    migrated_database_engine: Engine,
) -> None:
    with migrated_database_engine.connect() as connection:
        current_revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        assert current_revision == CURRENT_REVISION


def test_staff_session_digest_constraints_are_enforced(
    migrated_database_engine: Engine,
) -> None:
    with migrated_database_engine.connect() as connection:
        transaction = connection.begin()
        try:
            staff_id = _insert_staff(connection)
            digest = b"s" * 32
            connection.execute(
                StaffSession.__table__.insert().values(
                    id=uuid4(),
                    staff_user_id=staff_id,
                    refresh_token_digest=digest,
                    expires_at=text("CURRENT_TIMESTAMP + INTERVAL '7 days'"),
                )
            )
            _expect_integrity_error(
                connection,
                StaffSession.__table__.insert().values(
                    id=uuid4(),
                    staff_user_id=staff_id,
                    refresh_token_digest=digest,
                    expires_at=text("CURRENT_TIMESTAMP + INTERVAL '7 days'"),
                ),
            )
            _expect_integrity_error(
                connection,
                StaffSession.__table__.insert().values(
                    id=uuid4(),
                    staff_user_id=staff_id,
                    refresh_token_digest=b"short",
                    expires_at=text("CURRENT_TIMESTAMP + INTERVAL '7 days'"),
                ),
            )
        finally:
            transaction.rollback()


def test_unique_track_digest_is_enforced(migrated_database_engine: Engine) -> None:
    with migrated_database_engine.connect() as connection:
        transaction = connection.begin()
        try:
            digest = b"u" * 32
            _insert_appeal(connection, digest=digest)
            _expect_integrity_error(
                connection,
                Appeal.__table__.insert().values(
                    id=uuid4(),
                    track_digest=digest,
                    applicant_type=ApplicantType.PARENT,
                ),
            )
        finally:
            transaction.rollback()


def test_track_digest_must_be_sha256_length(migrated_database_engine: Engine) -> None:
    with migrated_database_engine.connect() as connection:
        transaction = connection.begin()
        try:
            _expect_integrity_error(
                connection,
                Appeal.__table__.insert().values(
                    id=uuid4(),
                    track_digest=b"short",
                    applicant_type=ApplicantType.TEACHER,
                ),
            )
        finally:
            transaction.rollback()


def test_rating_and_message_author_checks_are_enforced(
    migrated_database_engine: Engine,
) -> None:
    with migrated_database_engine.connect() as connection:
        transaction = connection.begin()
        try:
            appeal_id = _insert_appeal(connection, digest=b"v" * 32)
            staff_id = _insert_staff(connection)
            _expect_integrity_error(
                connection,
                AppealFeedback.__table__.insert().values(id=uuid4(), appeal_id=appeal_id, rating=6),
            )
            _expect_integrity_error(
                connection,
                AppealMessage.__table__.insert().values(
                    id=uuid4(),
                    appeal_id=appeal_id,
                    author_type=MessageAuthorType.APPLICANT,
                    author_staff_user_id=staff_id,
                    encrypted_body=b"ciphertext",
                    key_version=1,
                ),
            )
        finally:
            transaction.rollback()


def test_only_one_active_primary_participant_is_enforced(
    migrated_database_engine: Engine,
) -> None:
    with migrated_database_engine.connect() as connection:
        transaction = connection.begin()
        try:
            appeal_id = _insert_appeal(connection, digest=b"w" * 32)
            first_staff_id = _insert_staff(connection)
            second_staff_id = _insert_staff(connection)
            connection.execute(
                AppealParticipant.__table__.insert().values(
                    id=uuid4(),
                    appeal_id=appeal_id,
                    staff_user_id=first_staff_id,
                    participant_role="primary",
                )
            )
            _expect_integrity_error(
                connection,
                AppealParticipant.__table__.insert().values(
                    id=uuid4(),
                    appeal_id=appeal_id,
                    staff_user_id=second_staff_id,
                    participant_role="primary",
                ),
            )
        finally:
            transaction.rollback()


def test_crisis_rule_uniqueness_and_rejection_constraints(
    migrated_database_engine: Engine,
) -> None:
    with migrated_database_engine.connect() as connection:
        transaction = connection.begin()
        try:
            unique_suffix = uuid4().hex
            values = {
                "phrase": f"integration crisis phrase {unique_suffix}",
                "normalized_phrase": f"integration crisis phrase {unique_suffix}",
                "compact_phrase": f"integrationcrisisphrase{unique_suffix}",
                "allow_compact_match": True,
            }
            connection.execute(CrisisRule.__table__.insert().values(id=uuid4(), **values))
            _expect_integrity_error(
                connection,
                CrisisRule.__table__.insert().values(id=uuid4(), **values),
            )
            _expect_integrity_error(
                connection,
                CrisisRule.__table__.insert().values(
                    id=uuid4(),
                    phrase="empty normalized form",
                    normalized_phrase="",
                    compact_phrase="",
                ),
            )
            appeal_id = _insert_appeal(connection, digest=b"z" * 32)
            _expect_integrity_error(
                connection,
                text(
                    "INSERT INTO appeal_rejections "
                    "(appeal_id, kind, encrypted_reason, key_version) "
                    "VALUES (:appeal_id, 'unsupported', :reason, 1)"
                ).bindparams(appeal_id=appeal_id, reason=b"ciphertext"),
            )
        finally:
            transaction.rollback()


def test_phase5_encrypted_reason_and_return_constraints(
    migrated_database_engine: Engine,
) -> None:
    with migrated_database_engine.connect() as connection:
        transaction = connection.begin()
        try:
            appeal_id = _insert_appeal(connection, digest=b"5" * 32)
            requester_id = _insert_staff(connection)
            return_id = uuid4()
            connection.execute(
                AppealReturnExplanation.__table__.insert().values(
                    id=return_id,
                    appeal_id=appeal_id,
                    return_number=1,
                    encrypted_body=b"ciphertext",
                    key_version=1,
                )
            )
            _expect_integrity_error(
                connection,
                AppealReturnExplanation.__table__.insert().values(
                    id=uuid4(),
                    appeal_id=appeal_id,
                    return_number=1,
                    encrypted_body=b"different-ciphertext",
                    key_version=1,
                ),
            )
            _expect_integrity_error(
                connection,
                TransferRequest.__table__.insert().values(
                    id=uuid4(),
                    appeal_id=appeal_id,
                    requested_by_staff_user_id=requester_id,
                    encrypted_reason=b"ciphertext",
                    key_version=None,
                ),
            )
        finally:
            transaction.rollback()


def test_transfer_resolution_consistency_constraint_is_enforced_unchanged(
    migrated_database_engine: Engine,
) -> None:
    constraint_name = "ck_transfer_requests_transfer_requests_resolution_consistency"
    with migrated_database_engine.connect() as connection:
        transaction = connection.begin()
        try:
            definition = connection.scalar(
                text(
                    "SELECT pg_get_constraintdef(oid) "
                    "FROM pg_constraint WHERE conname = :constraint_name"
                ),
                {"constraint_name": constraint_name},
            )
            assert definition is not None
            normalized_definition = " ".join(str(definition).lower().split())
            assert "'pending'" in normalized_definition
            assert "resolved_at is null" in normalized_definition
            assert "resolved_by_staff_user_id is null" in normalized_definition
            assert "'approved'" in normalized_definition
            assert "'rejected'" in normalized_definition
            assert "resolved_at is not null" in normalized_definition

            appeal_id = _insert_appeal(connection, digest=b"6" * 32)
            requester_id = _insert_staff(connection)
            resolver_id = _insert_staff(connection)
            _expect_integrity_error(
                connection,
                TransferRequest.__table__.insert().values(
                    id=uuid4(),
                    appeal_id=appeal_id,
                    requested_by_staff_user_id=requester_id,
                    encrypted_reason=b"ciphertext",
                    key_version=1,
                    status="pending",
                    resolved_by_staff_user_id=resolver_id,
                    resolved_at=text("CURRENT_TIMESTAMP"),
                ),
            )
        finally:
            transaction.rollback()
