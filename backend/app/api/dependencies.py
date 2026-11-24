"""Identity and authorization dependencies."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import decode_token
from backend.app.db.session import get_session
from backend.app.models import AdminUser, User
from backend.app.services.authorization import can_perform_admin_action

bearer_scheme = HTTPBearer(auto_error=False)
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_customer(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: SessionDep,
) -> User:
    """Resolve customer identity only from a server-signed bearer JWT."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Kirish talab qilinadi"
        )
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        if payload.get("role") != "customer":
            raise ValueError("Customer token emas")
        user_id = int(payload["sub"])
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token yaroqsiz yoki muddati tugagan",
        ) from exc

    user = await session.get(User, user_id)
    if user is None or user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Foydalanuvchi faol emas"
        )
    return user


async def get_current_admin(
    request: Request,
    session: SessionDep,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> AdminUser:
    """Resolve admin identity from the JWT cookie or Authorization header."""
    token = request.cookies.get("admin_access")
    if not token and credentials is not None:
        token = credentials.credentials
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin kirishi talab qilinadi",
        )
    try:
        payload = decode_token(token, expected_type="access")
        if payload.get("role") not in {"owner", "manager"}:
            raise ValueError("Admin token emas")
        admin_id = int(payload["sub"])
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin token yaroqsiz yoki muddati tugagan",
        ) from exc

    admin = await session.get(AdminUser, admin_id)
    if admin is None or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin faol emas"
        )
    return admin


def require_admin_action(action: str) -> Callable:
    """Authorize a role for an admin operation."""

    async def dependency(
        admin: Annotated[AdminUser, Depends(get_current_admin)],
    ) -> AdminUser:
        if not can_perform_admin_action(admin.role, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu amal uchun owner huquqi kerak",
            )
        return admin

    return dependency
