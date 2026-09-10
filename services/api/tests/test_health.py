from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


class FakeDatabase:
    def __init__(self, healthy: bool) -> None:
        self.healthy = healthy

    async def is_healthy(self) -> bool:
        return self.healthy


class FakeValkey:
    def __init__(self, healthy: bool) -> None:
        self.healthy = healthy

    async def ping(self) -> bool:
        return self.healthy


async def test_basic_health(test_settings: Settings) -> None:
    app = create_app(test_settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_readiness_reports_healthy_services(test_settings: Settings) -> None:
    app = create_app(test_settings)
    app.state.database = FakeDatabase(healthy=True)
    app.state.valkey = FakeValkey(healthy=True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "services": {"application": "ok", "database": "ok", "valkey": "ok"},
    }


async def test_readiness_returns_503_when_a_service_fails(test_settings: Settings) -> None:
    app = create_app(test_settings)
    app.state.database = FakeDatabase(healthy=False)
    app.state.valkey = FakeValkey(healthy=True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "services": {"application": "ok", "database": "unavailable", "valkey": "ok"},
    }
