"""Focused tests for customer/admin authentication security helpers."""

import hashlib
import hmac
import json
from urllib.parse import urlencode

import jwt
import pytest
from fastapi import Response

from backend.app.api.v1.auth import _clear_admin_cookies, _set_admin_cookies
from backend.app.core import security
from backend.app.services.authorization import can_perform_admin_action
from backend.app.services.login_protection import LoginAttemptTracker


def signed_init_data(bot_token: str, auth_date: int) -> str:
    """Create test Telegram initData using Telegram's documented HMAC scheme."""
    data = {
        "auth_date": str(auth_date),
        "query_id": "test-query",
        "user": json.dumps({"id": 12345, "first_name": "Ali"}, separators=(",", ":")),
    }
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(data.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256,
    ).digest()
    data["hash"] = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(data)


def test_telegram_init_data_accepts_valid_signature_and_parses_user():
    init_data = signed_init_data("test-token", auth_date=1_700_000_000)

    result = security.verify_telegram_init_data(
        init_data,
        bot_token="test-token",
        now=1_700_000_100,
    )

    assert result["user"] == {"id": 12345, "first_name": "Ali"}
    assert result["auth_date"] == 1_700_000_000


def test_telegram_init_data_rejects_tampering():
    init_data = signed_init_data("test-token", auth_date=1_700_000_000)
    tampered = init_data.replace("Ali", "Vali")

    with pytest.raises(security.TelegramInitDataError, match="imzosi"):
        security.verify_telegram_init_data(
            tampered,
            bot_token="test-token",
            now=1_700_000_100,
        )


def test_telegram_init_data_rejects_expired_auth_date():
    init_data = signed_init_data("test-token", auth_date=1_700_000_000)

    with pytest.raises(security.TelegramInitDataError, match="eskirgan"):
        security.verify_telegram_init_data(
            init_data,
            bot_token="test-token",
            now=1_700_000_000 + security.TELEGRAM_AUTH_MAX_AGE_SECONDS + 1,
        )


def test_admin_access_tokens_have_role_and_access_type(monkeypatch):
    monkeypatch.setattr(security, "JWT_SECRET_KEY", "s" * 40)

    token, expires_in = security.create_access_token(12, role="manager")
    payload = jwt.decode(token, "s" * 40, algorithms=["HS256"])

    assert payload["sub"] == "12"
    assert payload["role"] == "manager"
    assert payload["type"] == "access"
    assert expires_in == security.ADMIN_ACCESS_TOKEN_MINUTES * 60


def test_manager_cannot_delete_cars_or_change_settings():
    assert can_perform_admin_action("manager", "cars.read")
    assert not can_perform_admin_action("manager", "cars.delete")
    assert not can_perform_admin_action("manager", "settings.write")
    assert can_perform_admin_action("owner", "settings.write")
    assert not can_perform_admin_action("unknown", "cars.read")


def test_admin_access_cookie_covers_admin_api_and_refresh_cookie_stays_scoped():
    response = Response()

    _set_admin_cookies(response, "access", "refresh")

    cookies = response.headers.getlist("set-cookie")
    assert any(
        "admin_access=access" in cookie and "Path=/api/v1;" in cookie
        for cookie in cookies
    )
    assert any(
        "admin_refresh=refresh" in cookie and "Path=/api/v1/auth/admin;" in cookie
        for cookie in cookies
    )

    cleared = Response()
    _clear_admin_cookies(cleared)
    deletion_cookies = cleared.headers.getlist("set-cookie")
    assert any(
        "admin_access=" in cookie and "Path=/api/v1;" in cookie
        for cookie in deletion_cookies
    )
    assert any(
        "admin_refresh=" in cookie and "Path=/api/v1/auth/admin;" in cookie
        for cookie in deletion_cookies
    )


@pytest.mark.asyncio
async def test_login_tracker_locks_after_five_failures():
    tracker = LoginAttemptTracker()

    for _ in range(4):
        assert await tracker.record_failure("ip:user") == 0
    assert await tracker.record_failure("ip:user") == 15 * 60
    assert await tracker.remaining_lock_seconds("ip:user") > 0

    await tracker.reset("ip:user")
    assert await tracker.remaining_lock_seconds("ip:user") == 0
