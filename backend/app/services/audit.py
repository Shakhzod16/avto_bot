"""Audit logging for administrative actions."""

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import AuditLog


async def write_audit_entry(
    session: AsyncSession,
    *,
    action: str,
    entity: str,
    admin_user_id: int | None,
    entity_id: str | int | None = None,
    before: Any = None,
    after: Any = None,
    ip_address: str | None = None,
) -> None:
    """Persist an auditable admin action in the same transaction."""
    session.add(
        AuditLog(
            admin_user_id=admin_user_id,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            before_json=json.dumps(before, ensure_ascii=False, default=str)
            if before is not None
            else None,
            after_json=json.dumps(after, ensure_ascii=False, default=str)
            if after is not None
            else None,
            ip_address=ip_address,
        )
    )
