from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.api.dependencies import get_current_admin
from backend.app.db.base import Base
from backend.app.db.session import get_session
from backend.app.main import app
from backend.app.models import AdminUser, AuditLog


@pytest.mark.asyncio
async def test_owner_can_create_car_and_action_is_audited(tmp_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'admin.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        session.add(
            AdminUser(
                id=1,
                username="owner",
                password_hash="not-used",
                role="owner",
            )
        )
        await session.commit()

    async def override_session():
        async with factory() as session:
            yield session

    async def override_admin():
        return AdminUser(id=1, username="owner", password_hash="not-used", role="owner")

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_admin] = override_admin
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/admin/cars",
                json={
                    "slug": "volkswagen-test-model",
                    "brand": "Volkswagen",
                    "model": "Test Model",
                    "body_type": "C-SUV",
                    "engine": "2.0 TSI",
                    "power_hp": 200,
                    "emission": "Euro-6",
                    "drive": "AWD",
                    "transmission": "7AT",
                    "seats": 5,
                },
            )

        assert response.status_code == 201
        assert response.json()["is_active"] is True
        async with factory() as session:
            audit = await session.scalar(
                select(AuditLog).where(AuditLog.action == "car.create")
            )
            assert audit is not None
            assert audit.entity_id == "1"
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_admin, None)
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "method", "body"),
    [
        ("/api/v1/admin/cars/1", "delete", None),
        ("/api/v1/admin/settings", "put", {"address": "Yangi manzil"}),
    ],
)
async def test_manager_cannot_delete_cars_or_change_settings(
    tmp_path: Path, path, method, body
):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'manager.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_session():
        async with factory() as session:
            yield session

    async def override_admin():
        return AdminUser(
            id=2, username="manager", password_hash="not-used", role="manager"
        )

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_admin] = override_admin
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.request(method, path, json=body)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "http_403"
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_admin, None)
        await engine.dispose()
