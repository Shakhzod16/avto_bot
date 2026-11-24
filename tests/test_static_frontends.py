import httpx
import pytest

from backend.app.main import ADMIN_DIST, WEBAPP_DIST, app


@pytest.mark.asyncio
async def test_frontend_mounts_and_client_route_fallbacks():
    if not ADMIN_DIST.is_dir() or not WEBAPP_DIST.is_dir():
        pytest.skip("Frontend production builds are not present")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=True,
    ) as client:
        for path in (
            "/app/",
            "/app/cars/volkswagen-teramont-pro",
            "/admin/",
            "/admin/settings",
        ):
            response = await client.get(path)
            assert response.status_code == 200
            assert '<div id="root"></div>' in response.text
