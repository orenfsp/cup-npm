import base64
from datetime import UTC, datetime, timedelta
from typing import Annotated, cast
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.core.config import AppEnvironment, Settings
from app.core.errors import InfrastructureError, UnauthorizedError
from app.core.security.passwords import hash_password, verify_password
from app.core.security.tokens import AccessTokenService
from app.db.models import Category, ExpertProfile, SpecialistGroup, StaffSession, StaffUser
from app.db.models.enums import StaffRole
from app.db.repositories.staff_auth import StaffAuthRepository
from app.main import create_app
from app.modules.auth.dependencies import get_auth_service, require_role
from app.modules.auth.policy import AccessPolicy
from app.modules.auth.rate_limit import LoginRateLimiter
from app.modules.auth.service import AuthService
from app.modules.categories.reference_data import STARTER_CATEGORIES
from app.modules.staff.service import StaffManagementService
from app.scripts.seed_demo_staff import (
    DemoRoutingSeedRepository,
    _definitions,
    _password_or_fallback,
    _routing_definitions,
    _seed_definitions,
    _seed_demo_routing,
    seed_demo_staff,
)


def test_specialist_demo_passwords_fall_back_only_when_unset() -> None:
    fallback = SecretStr("shared demo password")
    assert _password_or_fallback(None, fallback) is fallback
    assert _password_or_fallback(SecretStr(""), fallback) is fallback
    override = SecretStr("specialist override")
    assert _password_or_fallback(override, fallback) is override


class FakeRepository:
    def __init__(self, users: list[StaffUser] | None = None) -> None:
        self.users = {user.id: user for user in users or []}
        self.sessions: dict[UUID, StaffSession] = {}
        self.expert_profiles: dict[UUID, ExpertProfile] = {}
        self.commit_count = 0

    async def get_staff_by_login(self, login: str) -> StaffUser | None:
        return next((user for user in self.users.values() if user.login == login), None)

    async def get_staff_by_id(self, staff_user_id: UUID) -> StaffUser | None:
        return self.users.get(staff_user_id)

    async def add_staff_user(self, staff_user: StaffUser) -> None:
        self.users[staff_user.id] = staff_user

    async def get_expert_profile(self, staff_user_id: UUID) -> ExpertProfile | None:
        return self.expert_profiles.get(staff_user_id)

    async def add_expert_profile(self, profile: ExpertProfile) -> None:
        self.expert_profiles[profile.staff_user_id] = profile

    async def add_session(self, staff_session: StaffSession) -> None:
        self.sessions[staff_session.id] = staff_session

    async def get_session_by_id(self, session_id: UUID) -> StaffSession | None:
        return self.sessions.get(session_id)

    async def get_session_by_refresh_digest_for_update(self, digest: bytes) -> StaffSession | None:
        return next(
            (
                session
                for session in self.sessions.values()
                if session.refresh_token_digest == digest
            ),
            None,
        )

    async def revoke_all_sessions(self, staff_user_id: UUID, *, revoked_at: datetime) -> None:
        for session in self.sessions.values():
            if session.staff_user_id == staff_user_id and session.revoked_at is None:
                session.revoked_at = revoked_at

    async def commit(self) -> None:
        self.commit_count += 1

    async def rollback(self) -> None:
        pass


class FakeDemoRoutingRepository:
    def __init__(self, users: list[StaffUser]) -> None:
        self.users = {user.login: user for user in users}
        self.groups: dict[str, SpecialistGroup] = {}
        self.categories = [
            Category(
                id=uuid4(),
                slug=item.slug,
                name=item.name,
                description=item.description,
                is_active=True,
                sort_order=item.sort_order,
            )
            for item in STARTER_CATEGORIES
        ]
        self.memberships: set[tuple[UUID, UUID]] = set()
        self.rules: set[tuple[UUID, UUID]] = set()
        self.commits = 0

    async def expert(self, login):
        return self.users.get(login)

    async def group(self, slug):
        return self.groups.get(slug)

    async def add_group(self, group):
        self.groups[group.slug] = group

    async def active_categories(self):
        return self.categories

    async def has_membership(self, expert_id, group_id):
        return (expert_id, group_id) in self.memberships

    def add_membership(self, expert_id, group_id):
        self.memberships.add((expert_id, group_id))

    async def has_rule(self, category_id, group_id):
        return (category_id, group_id) in self.rules

    def add_rule(self, category_id, group_id):
        self.rules.add((category_id, group_id))

    async def commit(self):
        self.commits += 1


class NoopRateLimiter:
    async def check(self, *, transient_ip: str, normalized_login: str) -> None:
        del transient_ip, normalized_login


class FakePipeline:
    def __init__(self, store: dict[str, int]) -> None:
        self.store = store
        self.operations: list[tuple[str, str]] = []

    def incr(self, key: str) -> "FakePipeline":
        self.operations.append(("incr", key))
        return self

    def expire(self, key: str, seconds: int, *, nx: bool) -> "FakePipeline":
        assert seconds > 0
        assert nx
        self.operations.append(("expire", key))
        return self

    async def execute(self) -> list[int | bool]:
        results: list[int | bool] = []
        for operation, key in self.operations:
            if operation == "incr":
                self.store[key] = self.store.get(key, 0) + 1
                results.append(self.store[key])
            else:
                results.append(True)
        return results


class FakeValkey:
    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    def pipeline(self, *, transaction: bool) -> FakePipeline:
        assert transaction
        return FakePipeline(self.store)


def _staff(
    role: StaffRole = StaffRole.OPERATOR,
    *,
    active: bool = True,
    password: str = "correct horse battery staple",
) -> StaffUser:
    return StaffUser(
        id=uuid4(),
        login=f"{role.value}_{uuid4().hex[:8]}",
        password_hash=hash_password(password),
        role=role,
        is_active=active,
        must_change_password=False,
        display_name=f"Test {role.value}",
    )


def _service(
    settings: Settings,
    staff: StaffUser,
    *,
    rate_limiter: object | None = None,
) -> tuple[AuthService, FakeRepository]:
    repository = FakeRepository([staff])
    service = AuthService(
        cast(StaffAuthRepository, repository),
        settings,
        cast(LoginRateLimiter, rate_limiter or NoopRateLimiter()),
    )
    return service, repository


def _app(settings: Settings, service: AuthService):
    app = create_app(settings)
    app.dependency_overrides[get_auth_service] = lambda: service
    return app


async def _login(
    service: AuthService, staff: StaffUser, password: str = "correct horse battery staple"
):
    return await service.login(login=staff.login, password=password, transient_ip="127.0.0.1")


async def test_create_staff_normalizes_login_and_hashes_password() -> None:
    repository = FakeRepository()
    service = StaffManagementService(cast(StaffAuthRepository, repository))

    staff = await service.create_staff_user(
        login="  New.Operator  ",
        password="a development password",
        role=StaffRole.OPERATOR,
        display_name="  New Operator  ",
    )

    assert staff.login == "new.operator"
    assert staff.display_name == "New Operator"
    assert staff.password_hash != "a development password"
    assert verify_password("a development password", staff.password_hash)


async def test_successful_login_returns_access_token_and_safe_profile(
    test_settings: Settings,
) -> None:
    staff = _staff()
    service, repository = _service(test_settings, staff)

    result = await _login(service, staff)

    assert result.access_token
    assert result.staff.login == staff.login
    assert not hasattr(result.staff, "password_hash")
    assert len(repository.sessions) == 1


@pytest.mark.parametrize("known_login", [True, False])
async def test_bad_credentials_have_same_public_error(
    test_settings: Settings, known_login: bool
) -> None:
    staff = _staff()
    service, _ = _service(test_settings, staff)
    login = staff.login if known_login else "does_not_exist"

    with pytest.raises(UnauthorizedError) as error:
        await service.login(login=login, password="wrong", transient_ip="127.0.0.1")

    assert error.value.message == "Invalid staff credentials."


async def test_inactive_staff_cannot_login(test_settings: Settings) -> None:
    staff = _staff(active=False)
    service, _ = _service(test_settings, staff)

    with pytest.raises(UnauthorizedError, match="Invalid staff credentials"):
        await _login(service, staff)


async def test_login_sets_httponly_refresh_cookie(test_settings: Settings) -> None:
    staff = _staff()
    service, _ = _service(test_settings, staff)
    app = _app(test_settings, service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"login": staff.login, "password": "correct horse battery staple"},
        )

    cookie = response.headers["set-cookie"].lower()
    assert response.status_code == 200
    assert "httponly" in cookie
    assert "path=/api/v1/auth" in cookie
    assert "samesite=lax" in cookie
    assert response.headers["cache-control"] == "no-store"
    assert "access_token" in response.json()
    assert "password_hash" not in response.text


async def test_login_endpoint_does_not_enumerate_staff(test_settings: Settings) -> None:
    staff = _staff()
    service, _ = _service(test_settings, staff)
    app = _app(test_settings, service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        wrong_password = await client.post(
            "/api/v1/auth/login",
            json={"login": staff.login, "password": "wrong"},
        )
        missing_login = await client.post(
            "/api/v1/auth/login",
            json={"login": "missing", "password": "wrong"},
        )

    assert wrong_password.status_code == 401
    assert missing_login.status_code == 401
    assert wrong_password.json() == missing_login.json()


async def test_production_refresh_cookie_is_secure(test_settings: Settings) -> None:
    encryption_key = base64.urlsafe_b64encode(b"k" * 32).decode()
    settings = Settings(
        _env_file=None,
        app_env="production",
        jwt_secret="j" * 64,
        track_hmac_secret="t" * 64,
        rate_limit_hmac_secret="r" * 64,
        refresh_token_hmac_secret="f" * 64,
        applicant_access_jwt_secret="a" * 64,
        content_encryption_key=encryption_key,
        cors_origins=["https://staff.example.test"],
    )
    staff = _staff()
    service, _ = _service(settings, staff)
    app = _app(settings, service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"login": staff.login, "password": "correct horse battery staple"},
        )

    assert "secure" in response.headers["set-cookie"].lower()


async def test_refresh_succeeds_and_rotates_token(test_settings: Settings) -> None:
    staff = _staff()
    service, repository = _service(test_settings, staff)
    original = await _login(service, staff)

    refreshed = await service.refresh(original.refresh_token)

    session = next(iter(repository.sessions.values()))
    assert refreshed.access_token
    assert refreshed.refresh_token != original.refresh_token
    assert session.rotation_counter == 1
    assert session.last_used_at is not None


async def test_refresh_endpoint_rotates_cookie(test_settings: Settings) -> None:
    staff = _staff()
    service, _ = _service(test_settings, staff)
    app = _app(test_settings, service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"login": staff.login, "password": "correct horse battery staple"},
        )
        original_cookie = client.cookies[test_settings.refresh_cookie_name]
        refresh_response = await client.post("/api/v1/auth/refresh")
        rotated_cookie = client.cookies[test_settings.refresh_cookie_name]

    assert login_response.status_code == 200
    assert refresh_response.status_code == 200
    assert rotated_cookie != original_cookie
    assert "httponly" in refresh_response.headers["set-cookie"].lower()


async def test_rotated_refresh_token_cannot_be_reused(test_settings: Settings) -> None:
    staff = _staff()
    service, _ = _service(test_settings, staff)
    original = await _login(service, staff)
    await service.refresh(original.refresh_token)

    with pytest.raises(UnauthorizedError):
        await service.refresh(original.refresh_token)


@pytest.mark.parametrize("session_state", ["expired", "revoked"])
async def test_invalid_refresh_session_fails(test_settings: Settings, session_state: str) -> None:
    staff = _staff()
    service, repository = _service(test_settings, staff)
    original = await _login(service, staff)
    session = next(iter(repository.sessions.values()))
    if session_state == "expired":
        session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    else:
        session.revoked_at = datetime.now(UTC)

    with pytest.raises(UnauthorizedError):
        await service.refresh(original.refresh_token)


async def test_logout_revokes_session_and_clears_cookie(test_settings: Settings) -> None:
    staff = _staff()
    service, repository = _service(test_settings, staff)
    app = _app(test_settings, service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"login": staff.login, "password": "correct horse battery staple"},
        )
        assert login_response.status_code == 200
        response = await client.post("/api/v1/auth/logout")

    session = next(iter(repository.sessions.values()))
    assert response.status_code == 200
    assert session.revoked_at is not None
    assert "max-age=0" in response.headers["set-cookie"].lower()


async def test_logout_without_cookie_is_idempotent(test_settings: Settings) -> None:
    staff = _staff()
    service, _ = _service(test_settings, staff)
    app = _app(test_settings, service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 200


async def test_auth_me_returns_safe_staff_profile(test_settings: Settings) -> None:
    staff = _staff()
    service, _ = _service(test_settings, staff)
    result = await _login(service, staff)
    app = _app(test_settings, service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {result.access_token}"}
        )

    assert response.status_code == 200
    assert response.json() == {
        "id": str(staff.id),
        "login": staff.login,
        "display_name": staff.display_name,
        "role": staff.role.value,
        "must_change_password": False,
    }


async def test_temporary_password_requires_change_before_role_access(
    test_settings: Settings,
) -> None:
    temporary_password = "TemporaryPassword2026"
    staff = _staff(password=temporary_password)
    staff.must_change_password = True
    service, repository = _service(test_settings, staff)
    result = await _login(service, staff, temporary_password)
    app = _app(test_settings, service)

    @app.get("/test-forced-password-role")
    async def protected(
        _staff_user: Annotated[StaffUser, Depends(require_role(StaffRole.OPERATOR))],
    ) -> dict[str, bool]:
        return {"ok": True}

    headers = {"Authorization": f"Bearer {result.access_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        blocked = await client.get("/test-forced-password-role", headers=headers)
        me = await client.get("/api/v1/auth/me", headers=headers)
        changed = await client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={"password": "PermanentPassword2026"},
        )

    assert result.staff.must_change_password is True
    assert blocked.status_code == 403
    assert me.status_code == 200
    assert me.json()["must_change_password"] is True
    assert changed.status_code == 200
    assert staff.must_change_password is False
    assert verify_password("PermanentPassword2026", staff.password_hash)
    assert all(session.revoked_at is not None for session in repository.sessions.values())
    with pytest.raises(UnauthorizedError):
        await service.login(
            login=staff.login,
            password=temporary_password,
            transient_ip="127.0.0.1",
        )
    replacement = await service.login(
        login=staff.login,
        password="PermanentPassword2026",
        transient_ip="127.0.0.1",
    )
    assert replacement.staff.must_change_password is False


async def test_invalid_jwt_fails(test_settings: Settings) -> None:
    staff = _staff()
    service, _ = _service(test_settings, staff)

    with pytest.raises(UnauthorizedError):
        await service.authenticate_access_token("not-a-jwt")


@pytest.mark.parametrize(
    ("issuer", "audience", "expired"),
    [
        ("wrong-issuer", "otklik-staff", False),
        ("otklik-api", "wrong-audience", False),
        ("otklik-api", "otklik-staff", True),
    ],
)
async def test_invalid_registered_jwt_claims_fail(
    test_settings: Settings, issuer: str, audience: str, expired: bool
) -> None:
    staff = _staff()
    service, repository = _service(test_settings, staff)
    result = await _login(service, staff)
    session = next(iter(repository.sessions.values()))
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(staff.id),
            "role": staff.role.value,
            "sid": str(session.id),
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(seconds=1) if expired else now + timedelta(minutes=2),
            "iss": issuer,
            "aud": audience,
        },
        test_settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )

    with pytest.raises(UnauthorizedError):
        await service.authenticate_access_token(token)
    assert result.access_token


async def test_inactive_staff_with_existing_jwt_fails(test_settings: Settings) -> None:
    staff = _staff()
    service, _ = _service(test_settings, staff)
    result = await _login(service, staff)
    staff.is_active = False

    with pytest.raises(UnauthorizedError):
        await service.authenticate_access_token(result.access_token)


async def test_access_jwt_contains_only_required_identity_and_validation_claims(
    test_settings: Settings,
) -> None:
    staff = _staff()
    service, _ = _service(test_settings, staff)
    result = await _login(service, staff)
    claims = jwt.decode(result.access_token, options={"verify_signature": False})

    assert set(claims) == {"sub", "role", "sid", "iat", "exp", "iss", "aud"}
    assert "login" not in claims
    assert "password_hash" not in claims


@pytest.mark.parametrize(
    ("actual_role", "required_role", "expected_status"),
    [
        (StaffRole.OPERATOR, StaffRole.OPERATOR, 200),
        (StaffRole.EXPERT, StaffRole.OPERATOR, 403),
        (StaffRole.ADMIN, StaffRole.ADMIN, 200),
    ],
)
async def test_role_guards(
    test_settings: Settings,
    actual_role: StaffRole,
    required_role: StaffRole,
    expected_status: int,
) -> None:
    staff = _staff(actual_role)
    service, _ = _service(test_settings, staff)
    result = await _login(service, staff)
    app = _app(test_settings, service)

    @app.get("/test-role")
    async def protected(
        _staff_user: Annotated[StaffUser, Depends(require_role(required_role))],
    ) -> dict[str, bool]:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/test-role", headers={"Authorization": f"Bearer {result.access_token}"}
        )

    assert response.status_code == expected_status


async def test_role_guard_requires_authentication(test_settings: Settings) -> None:
    staff = _staff()
    service, _ = _service(test_settings, staff)
    app = _app(test_settings, service)

    @app.get("/test-auth-required")
    async def protected(
        _staff_user: Annotated[StaffUser, Depends(require_role(StaffRole.OPERATOR))],
    ) -> dict[str, bool]:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/test-auth-required")

    assert response.status_code == 401


async def test_password_change_revokes_all_sessions(test_settings: Settings) -> None:
    staff = _staff()
    auth_service, repository = _service(test_settings, staff)
    result = await _login(auth_service, staff)
    management = StaffManagementService(cast(StaffAuthRepository, repository))

    await management.change_password(staff.id, new_password="new safe password")

    assert verify_password("new safe password", staff.password_hash)
    assert all(session.revoked_at is not None for session in repository.sessions.values())
    with pytest.raises(UnauthorizedError):
        await auth_service.authenticate_access_token(result.access_token)


async def test_deactivation_revokes_all_sessions(test_settings: Settings) -> None:
    staff = _staff()
    auth_service, repository = _service(test_settings, staff)
    await _login(auth_service, staff)
    management = StaffManagementService(cast(StaffAuthRepository, repository))

    await management.set_active(staff.id, is_active=False)

    assert not staff.is_active
    assert all(session.revoked_at is not None for session in repository.sessions.values())


async def test_login_rate_limiter_returns_429_and_stores_only_digests(
    test_settings: Settings,
) -> None:
    settings = test_settings.model_copy(update={"login_rate_limit_attempts": 2})
    valkey = FakeValkey()
    limiter = LoginRateLimiter(cast(object, valkey), settings)  # type: ignore[arg-type]
    staff = _staff()
    service, _ = _service(settings, staff, rate_limiter=limiter)
    app = _app(settings, service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(2):
            response = await client.post(
                "/api/v1/auth/login",
                json={"login": staff.login, "password": "wrong"},
            )
            assert response.status_code == 401
        response = await client.post(
            "/api/v1/auth/login",
            json={"login": staff.login, "password": "wrong"},
        )

    assert response.status_code == 429
    assert len(valkey.store) == 2
    assert all("127.0.0.1" not in key for key in valkey.store)
    assert all(staff.login not in key for key in valkey.store)


async def test_refresh_token_plaintext_is_not_persisted(test_settings: Settings) -> None:
    staff = _staff()
    service, repository = _service(test_settings, staff)
    result = await _login(service, staff)
    session = next(iter(repository.sessions.values()))

    assert isinstance(session.refresh_token_digest, bytes)
    assert len(session.refresh_token_digest) == 32
    assert result.refresh_token.encode() != session.refresh_token_digest
    assert not hasattr(session, "refresh_token")


def test_admin_role_does_not_grant_sensitive_content_access() -> None:
    assert AccessPolicy.can_manage_staff(StaffRole.ADMIN)
    assert not AccessPolicy.role_alone_grants_sensitive_appeal_access(StaffRole.ADMIN)
    assert not AccessPolicy.admin_may_read_appeal_content()
    assert not AccessPolicy.admin_may_read_crisis_contact()


def test_access_token_service_rejects_missing_secret() -> None:
    settings = Settings(_env_file=None, jwt_secret=None)

    with pytest.raises(InfrastructureError, match="not configured"):
        AccessTokenService(settings)


async def test_demo_staff_seed_is_idempotent_and_creates_expert_profile(
    test_settings: Settings,
) -> None:
    settings = test_settings.model_copy(
        update={
            "demo_operator_password": SecretStr("operator demo password"),
            "demo_expert_password": SecretStr("expert demo password"),
            "demo_psychologist_password": SecretStr("psychologist demo password"),
            "demo_lawyer_password": SecretStr("lawyer demo password"),
            "demo_social_password": SecretStr("social demo password"),
            "demo_conflict_password": SecretStr("conflict demo password"),
            "demo_admin_password": SecretStr("admin demo password"),
        }
    )
    repository = FakeRepository()
    typed_repository = cast(StaffAuthRepository, repository)

    first_count = await _seed_definitions(typed_repository, _definitions(settings))
    second_count = await _seed_definitions(typed_repository, _definitions(settings))

    assert first_count == 7
    assert second_count == 0
    assert len(repository.users) == 7
    experts = [user for user in repository.users.values() if user.role is StaffRole.EXPERT]
    assert len(experts) == 5
    assert all(expert.id in repository.expert_profiles for expert in experts)
    assert all(user.password_hash.startswith("$argon2") for user in repository.users.values())


async def test_multiple_demo_expert_routing_seed_is_idempotent(
    test_settings: Settings,
) -> None:
    settings = test_settings.model_copy(
        update={
            "demo_operator_password": SecretStr("operator demo password"),
            "demo_expert_password": SecretStr("expert demo password"),
            "demo_psychologist_password": SecretStr("psychologist demo password"),
            "demo_lawyer_password": SecretStr("lawyer demo password"),
            "demo_social_password": SecretStr("social demo password"),
            "demo_conflict_password": SecretStr("conflict demo password"),
            "demo_admin_password": SecretStr("admin demo password"),
        }
    )
    staff_repository = FakeRepository()
    await _seed_definitions(cast(StaffAuthRepository, staff_repository), _definitions(settings))
    routing_repository = FakeDemoRoutingRepository(list(staff_repository.users.values()))
    managed_group = SpecialistGroup(
        id=uuid4(),
        slug="psychologists",
        name="Administrator-managed name",
        description="Existing metadata",
        is_active=True,
    )
    routing_repository.groups[managed_group.slug] = managed_group

    first = await _seed_demo_routing(
        cast(DemoRoutingSeedRepository, routing_repository),
        _routing_definitions(settings),
    )
    second = await _seed_demo_routing(
        cast(DemoRoutingSeedRepository, routing_repository),
        _routing_definitions(settings),
    )

    assert first > 0
    assert second == 0
    assert set(routing_repository.groups) == {
        "demo_generalists",
        "psychologists",
        "lawyers",
        "social_teachers",
        "conflict_specialists",
    }
    assert routing_repository.groups["psychologists"].name == "Administrator-managed name"
    experts = [user for user in staff_repository.users.values() if user.role is StaffRole.EXPERT]
    assert len(routing_repository.memberships) == len(experts) == 5
    psychologist = next(user for user in experts if user.login == settings.demo_psychologist_login)
    psychologist_group = routing_repository.groups["psychologists"]
    assert (psychologist.id, psychologist_group.id) in routing_repository.memberships
    bullying = next(
        category
        for category in routing_repository.categories
        if category.slug == "bullying-insults"
    )
    eligible_group_ids = {
        group_id for category_id, group_id in routing_repository.rules if category_id == bullying.id
    }
    assert len(eligible_group_ids) >= 3


async def test_demo_staff_seed_refuses_production_without_override(
    test_settings: Settings,
) -> None:
    settings = test_settings.model_copy(update={"app_env": AppEnvironment.PRODUCTION})

    with pytest.raises(RuntimeError, match="disabled in production"):
        await seed_demo_staff(settings)
