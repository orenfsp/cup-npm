from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


async def test_meta_returns_only_public_runtime_information(test_settings: Settings) -> None:
    app = create_app(test_settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/meta")

    assert response.status_code == 200
    assert response.json() == {
        "application": "Otklik API",
        "environment": "testing",
        "api_version": "v1",
    }
    assert "secret" not in response.text.lower()
