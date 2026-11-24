"""Telegram initData verification and JWT/password security helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from urllib.parse import parse_qsl

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from backend.app.core.config import (
    ADMIN_ACCESS_TOKEN_MINUTES,
    ADMIN_REFRESH_TOKEN_DAYS,
    BOT_TOKEN,
    CUSTOMER_TOKEN_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    TELEGRAM_AUTH_MAX_AGE_SECONDS,
)

password_hasher = PasswordHasher()


class TelegramInitDataError(ValueError):
    """Telegram initData was invalid, forged or stale."""


def verify_telegram_init_data(
    init_data: str,
    *,
    bot_token: str | None = None,
    now: int | None = None,
    max_age_seconds: int = TELEGRAM_AUTH_MAX_AGE_SECONDS,
) -> dict:
    """Validate Telegram WebApp initData HMAC and auth_date freshness."""
    token = BOT_TOKEN if bot_token is None else bot_token
    if not token:
        raise TelegramInitDataError("Telegram bot token sozlanmagan")

    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise TelegramInitDataError("initData formati noto'g'ri") from exc

    fields: dict[str, str] = {}
    for key, value in pairs:
        if key in fields:
            raise TelegramInitDataError("initData da takroriy maydon bor")
        fields[key] = value

    provided_hash = fields.pop("hash", None)
    if not provided_hash or len(provided_hash) != 64:
        raise TelegramInitDataError("initData imzosi yo'q yoki noto'g'ri")

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(fields.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, provided_hash.lower()):
        raise TelegramInitDataError("initData imzosi noto'g'ri")

    try:
        auth_date = int(fields["auth_date"])
    except (KeyError, ValueError) as exc:
        raise TelegramInitDataError("auth_date maydoni noto'g'ri") from exc

    current_time = int(time.time()) if now is None else now
    if auth_date > current_time + 60:
        raise TelegramInitDataError("auth_date kelajak vaqtini ko'rsatmoqda")
    if current_time - auth_date > max_age_seconds:
        raise TelegramInitDataError("Telegram sessiyasi eskirgan")

    try:
        user = json.loads(fields["user"])
    except (KeyError, json.JSONDecodeError) as exc:
        raise TelegramInitDataError(
            "Telegram foydalanuvchi ma'lumoti noto'g'ri"
        ) from exc
    if not isinstance(user, dict) or not isinstance(user.get("id"), int):
        raise TelegramInitDataError("Telegram foydalanuvchi ID si noto'g'ri")

    return {**fields, "auth_date": auth_date, "user": user}


def _require_jwt_secret() -> str:
    if len(JWT_SECRET_KEY.encode("utf-8")) < 32:
        raise RuntimeError("JWT_SECRET_KEY kamida 32 bayt bo'lishi kerak")
    return JWT_SECRET_KEY


def create_access_token(subject: str | int, *, role: str) -> tuple[str, int]:
    """Create a short-lived access JWT."""
    expires_in = (
        CUSTOMER_TOKEN_MINUTES * 60
        if role == "customer"
        else ADMIN_ACCESS_TOKEN_MINUTES * 60
    )
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(subject),
            "role": role,
            "type": "access",
            "iat": now,
            "exp": now + timedelta(seconds=expires_in),
        },
        _require_jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )
    return token, expires_in


def create_admin_refresh_token(admin_id: int) -> tuple[str, str]:
    """Create a rotating admin refresh JWT and return token and token ID."""
    now = datetime.now(UTC)
    token_id = token_urlsafe(24)
    token = jwt.encode(
        {
            "sub": str(admin_id),
            "type": "admin_refresh",
            "jti": token_id,
            "iat": now,
            "exp": now + timedelta(days=ADMIN_REFRESH_TOKEN_DAYS),
        },
        _require_jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )
    return token, token_id


def decode_token(token: str, *, expected_type: str) -> dict:
    """Decode a signed JWT and validate its intended use."""
    try:
        payload = jwt.decode(
            token,
            _require_jwt_secret(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise ValueError("Token yaroqsiz yoki muddati tugagan") from exc
    if payload.get("type") != expected_type:
        raise ValueError("Token turi noto'g'ri")
    return payload


def hash_password(password: str) -> str:
    """Hash a password with Argon2id defaults."""
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password hash without exposing hash errors."""
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False
