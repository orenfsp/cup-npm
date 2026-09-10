from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


def test_application_creation(test_settings: Settings) -> None:
    app = create_app(test_settings)
    paths = set(app.openapi()["paths"])

    assert isinstance(app, FastAPI)
    assert app.title == "Otklik API"
    assert "/health" in paths
    assert "/api/v1/health/ready" in paths
    assert "/api/v1/meta" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/auth/refresh" in paths
    assert "/api/v1/auth/logout" in paths
    assert "/api/v1/auth/me" in paths


async def test_cors_supports_credentials_for_explicit_frontend_origin(
    test_settings: Settings,
) -> None:
    app = create_app(test_settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"
