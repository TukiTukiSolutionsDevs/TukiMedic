"""Audit service — helper to log significant actions to the audit_logs table."""
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def log_action(
    db: AsyncSession,
    user_id: Optional[uuid.UUID] = None,
    action: str = "",
    entity_type: Optional[str] = None,
    entity_id: Optional[uuid.UUID] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    """
    Create an audit log entry. Flushes (does not commit) so the entry
    participates in the caller's transaction.

    Usage:
        await log_action(db, user_id=user.id, action="login", ip_address=request.client.host)
    """
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=ip_address,
    )
    db.add(entry)
    await db.flush()
    return entry
