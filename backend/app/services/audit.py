"""Audit service — helpers to log significant actions to the audit_logs table.

Two flavors:
- log_action: generic, used by API endpoints (auth, documents, KB).
- log_clinical_decision: clinical-grade, used by orchestrator nodes
  (triage, guardrail, synthesizer). Adds model_version and inputs_hash
  for legal defensibility / tamper detection.
"""
import hashlib
import json
import uuid
from typing import Any, Optional

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


def _stable_hash(payload: Any) -> str:
    """SHA-256 over a stable JSON representation. Default=str handles UUIDs/datetimes."""
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


async def log_clinical_decision(
    db: AsyncSession,
    *,
    case_id: uuid.UUID,
    action: str,
    details: dict,
    model_version: str,
    user_id: Optional[uuid.UUID] = None,
) -> AuditLog:
    """
    Persist a clinical decision (triage / guardrail / synthesizer / etc.).

    The stored details dict is enriched with:
    - model_version: which agent + LLM produced this decision
    - inputs_hash: sha256 of the (details + model_version) payload, used as
      a tamper-evidence signal and as a dedup key.

    entity_type is hardcoded to "case" since clinical decisions are scoped
    to a clinical case.
    """
    enriched = {**details, "model_version": model_version}
    enriched["inputs_hash"] = _stable_hash(enriched)

    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type="case",
        entity_id=case_id,
        details=enriched,
    )
    db.add(entry)
    await db.flush()
    return entry
