"""Telegram lifespan setup tests without network access."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.app.bot import runtime


@pytest.mark.asyncio
async def test_polling_bot_is_started_and_stopped_cleanly(monkeypatch):
    stop_event = asyncio.Event()

    class FakeBot:
        def __init__(self, token):
            self.session = SimpleNamespace(close=AsyncMock())
            self.get_me = AsyncMock(
                return_value=SimpleNamespace(username="test_bot", id=1)
            )
            self.set_my_commands = AsyncMock()
            self.set_chat_menu_button = AsyncMock()
            self.delete_webhook = AsyncMock()

    class FakeDispatcher:
        def include_router(self, router):
            self.router = router

        async def start_polling(self, *args, **kwargs):
            await stop_event.wait()

        async def stop_polling(self):
            stop_event.set()

    monkeypatch.setattr(runtime, "BOT_TOKEN", "test-token")
    monkeypatch.setattr(runtime, "BOT_MODE", "polling")
    monkeypatch.setattr(runtime, "WEBAPP_URL", "https://mini.example.test/app")
    monkeypatch.setattr(runtime, "Bot", FakeBot)
    monkeypatch.setattr(runtime, "Dispatcher", FakeDispatcher)
    app = SimpleNamespace(state=SimpleNamespace())

    await runtime.start_telegram_bot(app)
    await asyncio.sleep(0)
    await runtime.stop_telegram_bot(app)

    app.state.telegram_bot.get_me.assert_awaited_once()
    app.state.telegram_bot.set_my_commands.assert_awaited_once()
    app.state.telegram_bot.set_chat_menu_button.assert_awaited_once()
    menu_button = app.state.telegram_bot.set_chat_menu_button.await_args.kwargs[
        "menu_button"
    ]
    assert menu_button.web_app.url == "https://mini.example.test/app"
    app.state.telegram_bot.delete_webhook.assert_awaited_once()
    app.state.telegram_bot.session.close.assert_awaited_once()


def test_webhook_mode_requires_public_https_url(monkeypatch):
    monkeypatch.setattr(runtime, "BOT_TOKEN", "test-token")
    monkeypatch.setattr(runtime, "BOT_MODE", "webhook")
    monkeypatch.setattr(runtime, "WEBAPP_URL", "https://mini.example.test/app")
    monkeypatch.setattr(runtime, "PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.setattr(runtime, "WEBHOOK_PATH", "/telegram/webhook")
    monkeypatch.setattr(runtime, "WEBHOOK_SECRET", "test_secret")

    with pytest.raises(RuntimeError, match="PUBLIC_BASE_URL"):
        runtime._validate_bot_settings()


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://example.test/app/",
        "https://localhost/app/",
        "https://127.0.0.1/app/",
        "https://[::1/app/",
        "https://not a domain/app/",
    ],
)
def test_invalid_webapp_url_warns_without_blocking_startup(monkeypatch, caplog, url):
    monkeypatch.setattr(runtime, "BOT_TOKEN", "test-token")
    monkeypatch.setattr(runtime, "BOT_MODE", "polling")
    monkeypatch.setattr(runtime, "WEBAPP_URL", url)

    runtime._validate_bot_settings()

    assert "WEBAPP_URL" in caplog.text


@pytest.mark.asyncio
async def test_invalid_webapp_url_keeps_bot_running_without_clearing_menu(
    monkeypatch, caplog
):
    stop_event = asyncio.Event()

    class FakeBot:
        def __init__(self, token):
            self.session = SimpleNamespace(close=AsyncMock())
            self.get_me = AsyncMock(
                return_value=SimpleNamespace(username="test_bot", id=1)
            )
            self.set_my_commands = AsyncMock()
            self.set_chat_menu_button = AsyncMock()
            self.delete_webhook = AsyncMock()

    class FakeDispatcher:
        def include_router(self, router):
            self.router = router

        async def start_polling(self, *args, **kwargs):
            await stop_event.wait()

        async def stop_polling(self):
            stop_event.set()

    monkeypatch.setattr(runtime, "BOT_TOKEN", "test-token")
    monkeypatch.setattr(runtime, "BOT_MODE", "polling")
    monkeypatch.setattr(runtime, "WEBAPP_URL", "http://localhost:8000/app/")
    monkeypatch.setattr(runtime, "Bot", FakeBot)
    monkeypatch.setattr(runtime, "Dispatcher", FakeDispatcher)
    app = SimpleNamespace(state=SimpleNamespace())

    await runtime.start_telegram_bot(app)
    await runtime.stop_telegram_bot(app)

    app.state.telegram_bot.set_chat_menu_button.assert_not_awaited()
    app.state.telegram_bot.delete_webhook.assert_awaited_once()
    assert "WEBAPP_URL" in caplog.text
