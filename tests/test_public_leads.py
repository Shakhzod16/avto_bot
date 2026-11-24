"""Integration tests for authenticated Mini App lead submission."""

from pathlib import Path
from typing import Annotated
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.api.dependencies import get_current_customer
from backend.app.db.base import Base
from backend.app.db.session import get_session
from backend.app.main import app
from backend.app.models import Lead, User


@pytest.mark.asyncio
async def test_authenticated_mini_app_lead_is_saved_and_notified(
    tmp_path: Path, monkeypatch
):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'leads.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        user = User(tg_id=987654321, name="Telegram User", language="uz")
        session.add(user)
        await session.commit()
        user_id = user.id

    async def override_session():
        async with factory() as session:
            yield session

    async def override_customer(
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> User | None:
        return await session.get(User, user_id)

    bot = object()
    previous_bot = getattr(app.state, "telegram_bot", None)
    app.state.telegram_bot = bot
    notify = AsyncMock()
    monkeypatch.setattr("backend.app.api.v1.routes.notify_new_lead", notify)
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_customer] = override_customer
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/leads",
                json={
                    "name": "Ali Valiyev",
                    "phone": "+998901234567",
                    "type": "test_drive",
                    "car_id": None,
                    "trim_id": None,
                    "comment": "Dam olish kuni",
                },
            )

        assert response.status_code == 201
        lead_id = response.json()["id"]
        async with factory() as session:
            lead = await session.scalar(select(Lead).where(Lead.id == lead_id))
            stored_user = await session.get(User, user_id)
        assert lead is not None
        assert lead.user_id == user_id
        assert lead.name == "Ali Valiyev"
        assert lead.comment == "Dam olish kuni"
        assert stored_user is not None
        assert stored_user.phone == "+998901234567"
        notify.assert_awaited_once_with(bot, lead_id)
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_customer, None)
        if previous_bot is None:
            delattr(app.state, "telegram_bot")
        else:
            app.state.telegram_bot = previous_bot
        await engine.dispose()
