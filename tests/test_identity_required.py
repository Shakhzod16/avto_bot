"""Verify that customer write/read resources require authenticated identity."""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import httpx
import pytest

from backend.app.core.config import BOT_TOKEN
from backend.app.main import app


@pytest.mark.asyncio
async def test_favorites_require_customer_jwt():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/favorites")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "http_401"


@pytest.mark.asyncio
async def test_lead_cannot_supply_an_untrusted_user_id():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/leads",
            json={
                "user_id": 12345,
                "name": "Ali Valiyev",
                "phone": "+998901234567",
                "type": "callback",
            },
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "http_401"


@pytest.mark.asyncio
async def test_telegram_auth_endpoint_rejects_unsigned_init_data():
    data = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": 1, "first_name": "Test"}, separators=(",", ":")),
    }
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(data.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        BOT_TOKEN.encode(),
        hashlib.sha256,
    ).digest()
    data["hash"] = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    data["user"] = json.dumps(
        {"id": 1, "first_name": "Tampered"}, separators=(",", ":")
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/telegram",
            json={"init_data": urlencode(data)},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "http_401"
