"""Customer Telegram authentication and admin session endpoints."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from backend.app.api.dependencies import SessionDep, get_current_admin
from backend.app.core.config import (
    ADMIN_ACCESS_TOKEN_MINUTES,
    ADMIN_PASSWORD,
    ADMIN_REFRESH_TOKEN_DAYS,
    ADMIN_USERNAME,
    BOT_TOKEN,
    COOKIE_SECURE,
)
from backend.app.core.security import (
    TelegramInitDataError,
    create_access_token,
    create_admin_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    verify_telegram_init_data,
)
from backend.app.models import AdminUser, User
from backend.app.schemas.auth import (
    AdminLoginRequest,
    AdminLoginResponse,
    CustomerTokenResponse,
    TelegramAuthRequest,
)
from backend.app.services.audit import write_audit_entry
from backend.app.services.login_protection import admin_login_tracker

logger = logging.getLogger(__name__)
router = APIRouter()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _set_admin_cookies(
    response: Response, access_token: str, refresh_token: str
) -> None:
    response.set_cookie(
        "admin_access",
        access_token,
        max_age=ADMIN_ACCESS_TOKEN_MINUTES * 60,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        path="/api/v1",
    )
    response.set_cookie(
        "admin_refresh",
        refresh_token,
        max_age=ADMIN_REFRESH_TOKEN_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        path="/api/v1/auth/admin",
    )


def _clear_admin_cookies(response: Response) -> None:
    response.delete_cookie(
        "admin_access", path="/api/v1", httponly=True, samesite="strict"
    )
    response.delete_cookie(
        "admin_refresh", path="/api/v1/auth/admin", httponly=True, samesite="strict"
    )


def _login_key(request: Request, username: str) -> str:
    return f"{_client_ip(request)}:{username.strip().casefold()}"


@router.post("/auth/telegram", response_model=CustomerTokenResponse)
async def telegram_auth(
    payload: TelegramAuthRequest, session: SessionDep
) -> CustomerTokenResponse:
    """Verify Telegram Mini App data, upsert its user and issue a JWT."""
    if not BOT_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram autentifikatsiyasi sozlanmagan",
        )
    try:
        validated = verify_telegram_init_data(payload.init_data)
    except TelegramInitDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    telegram_user = validated["user"]
    tg_id = telegram_user["id"]
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    user = result.scalar_one_or_none()
    full_name = " ".join(
        str(part).strip()
        for part in (telegram_user.get("first_name"), telegram_user.get("last_name"))
        if part and str(part).strip()
    )[:120]
    username = telegram_user.get("username")
    if user is None:
        user = User(
            tg_id=tg_id,
            name=full_name or None,
            username=str(username)[:64] if username else None,
            language=str(telegram_user.get("language_code", "uz"))[:8],
        )
        session.add(user)
    else:
        user.name = full_name or user.name
        user.username = str(username)[:64] if username else user.username

    await session.flush()
    if user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Hisobingiz bloklangan"
        )
    token, expires_in = create_access_token(user.id, role="customer")
    await session.commit()
    return CustomerTokenResponse(access_token=token, expires_in=expires_in)


@router.post("/auth/admin/login", response_model=AdminLoginResponse)
async def admin_login(
    payload: AdminLoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
) -> AdminLoginResponse:
    """Authenticate an admin and set rotating HttpOnly session cookies."""
    key = _login_key(request, payload.username)
    remaining = await admin_login_tracker.remaining_lock_seconds(key)
    if remaining:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Kirish vaqtincha bloklangan. {remaining} soniyadan keyin urinib ko'ring",
            headers={"Retry-After": str(remaining)},
        )

    result = await session.execute(
        select(AdminUser).where(AdminUser.username == payload.username.strip())
    )
    admin = result.scalar_one_or_none()
    valid_password = (
        await run_in_threadpool(verify_password, payload.password, admin.password_hash)
        if admin is not None
        else False
    )
    if admin is None or not admin.is_active or not valid_password:
        lock_seconds = await admin_login_tracker.record_failure(key)
        if admin is not None:
            admin.failed_login_attempts += 1
            if admin.failed_login_attempts >= 5:
                admin.locked_until = datetime.now(UTC) + timedelta(minutes=15)
                admin.failed_login_attempts = 0
                lock_seconds = 15 * 60
        await session.commit()
        if lock_seconds:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Juda ko'p noto'g'ri urinish. 15 daqiqadan keyin qayta urinib ko'ring",
                headers={"Retry-After": str(lock_seconds)},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Foydalanuvchi nomi yoki parol noto'g'ri",
        )

    now = datetime.now(UTC)
    if admin.locked_until is not None:
        locked_until = admin.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=UTC)
        if locked_until > now:
            remaining = max(1, int((locked_until - now).total_seconds()))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Kirish vaqtincha bloklangan",
                headers={"Retry-After": str(remaining)},
            )
    admin.failed_login_attempts = 0
    admin.locked_until = None
    admin.last_login_at = now
    await admin_login_tracker.reset(key)
    access_token, _ = create_access_token(admin.id, role=admin.role)
    refresh_token, refresh_jti = create_admin_refresh_token(admin.id)
    admin.refresh_token_id = refresh_jti
    await write_audit_entry(
        session,
        action="admin.login",
        entity="admin_user",
        admin_user_id=admin.id,
        entity_id=admin.id,
        ip_address=_client_ip(request),
    )
    await session.commit()
    _set_admin_cookies(response, access_token, refresh_token)
    return AdminLoginResponse(role=admin.role, username=admin.username)


@router.post("/auth/admin/refresh", response_model=AdminLoginResponse)
async def admin_refresh(
    request: Request,
    response: Response,
    session: SessionDep,
) -> AdminLoginResponse:
    """Rotate admin access and refresh cookies."""
    token = request.cookies.get("admin_refresh")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yangilash sessiyasi topilmadi",
        )
    try:
        payload = decode_token(token, expected_type="admin_refresh")
        admin_id = int(payload["sub"])
        token_id = payload["jti"]
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Yangilash tokeni yaroqsiz"
        ) from exc

    admin = await session.get(AdminUser, admin_id)
    if admin is None or not admin.is_active or admin.refresh_token_id != token_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yangilash tokeni bekor qilingan",
        )

    access_token, _ = create_access_token(admin.id, role=admin.role)
    refresh_token, refresh_jti = create_admin_refresh_token(admin.id)
    admin.refresh_token_id = refresh_jti
    await write_audit_entry(
        session,
        action="admin.refresh",
        entity="admin_user",
        admin_user_id=admin.id,
        entity_id=admin.id,
        ip_address=_client_ip(request),
    )
    await session.commit()
    _set_admin_cookies(response, access_token, refresh_token)
    return AdminLoginResponse(role=admin.role, username=admin.username)


@router.post("/auth/admin/logout", status_code=status.HTTP_204_NO_CONTENT)
async def admin_logout(
    request: Request,
    response: Response,
    session: SessionDep,
) -> Response:
    """Revoke the current admin refresh token and clear cookies."""
    token = request.cookies.get("admin_refresh")
    if token:
        try:
            payload = decode_token(token, expected_type="admin_refresh")
            admin = await session.get(AdminUser, int(payload["sub"]))
            if admin is not None and admin.refresh_token_id == payload.get("jti"):
                admin.refresh_token_id = None
                await write_audit_entry(
                    session,
                    action="admin.logout",
                    entity="admin_user",
                    admin_user_id=admin.id,
                    entity_id=admin.id,
                    ip_address=_client_ip(request),
                )
                await session.commit()
        except (ValueError, KeyError, TypeError):
            logger.info("Admin logout with invalid or expired refresh token")
    _clear_admin_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/auth/admin/me", response_model=AdminLoginResponse)
async def admin_me(
    admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> AdminLoginResponse:
    """Return the authenticated admin profile."""
    return AdminLoginResponse(role=admin.role, username=admin.username)


async def bootstrap_owner(session: AsyncSession) -> AdminUser:
    """Create the first owner using credentials from environment configuration."""
    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        raise RuntimeError(
            "ADMIN_USERNAME va ADMIN_PASSWORD .env faylida to'ldirilishi kerak"
        )
    existing_owner = await session.scalar(
        select(AdminUser).where(AdminUser.role == "owner")
    )
    if existing_owner is not None:
        raise RuntimeError("Owner admin allaqachon mavjud")
    existing_username = await session.scalar(
        select(AdminUser).where(AdminUser.username == ADMIN_USERNAME)
    )
    if existing_username is not None:
        raise RuntimeError("ADMIN_USERNAME bilan admin allaqachon mavjud")

    owner = AdminUser(
        username=ADMIN_USERNAME,
        password_hash=await run_in_threadpool(hash_password, ADMIN_PASSWORD),
        role="owner",
        is_active=True,
    )
    session.add(owner)
    await session.flush()
    await write_audit_entry(
        session,
        action="admin.owner_bootstrap",
        entity="admin_user",
        admin_user_id=owner.id,
        entity_id=owner.id,
    )
    await session.commit()
    return owner
