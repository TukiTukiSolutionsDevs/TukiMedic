"""Audit service — helpers to log significant actions to the audit_logs table.

Two flavors:
- ``log_action``: generic, used by API endpoints (auth, documents, KB).
- ``log_clinical_decision``: clinical-grade, used by orchestrator nodes
  (triage, guardrail, synthesizer). Adds ``model_version`` and
  ``inputs_hash`` for legal defensibility / tamper detection.

Tamper-evident hash chain
-------------------------

Every audit row carries two hash columns:

- ``previous_hash``: the ``chain_hash`` of the prior row (genesis: ``"0"*64``)
- ``chain_hash``:   ``sha256(previous_hash || details['inputs_hash'])``

The chain is GLOBAL (not per-case, not per-user) so any reordering or
deletion is detectable end-to-end. Concurrent writers are serialized by a
PostgreSQL transaction-scoped advisory lock so the SELECT-prev / INSERT-
chained pair is atomic. The lock key is ``hashtext('audit_chain')``.

Helpers
-------

- ``verify_chain(db) -> tuple[bool, list[uuid.UUID]]``: walks the table in
  (created_at ASC, id ASC) order; returns ``(True, [])`` if the chain is
  intact, otherwise ``(False, broken_ids)`` where each id is a row whose
  ``chain_hash`` does not equal ``sha256(previous_hash || inputs_hash)``
  OR whose ``previous_hash`` does not equal the prior row's ``chain_hash``.

Failure mode
------------

If the advisory lock cannot be acquired or the prior-row SELECT returns a
row that has been tampered with, ``log_action`` / ``log_clinical_decision``
still complete — they refuse to FORK the chain. The intent is for failures
to be loud (verify_chain catches them), not silent.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


GENESIS_HASH: str = "0" * 64
_ADVISORY_LOCK_SQL = "SELECT pg_advisory_xact_lock(hashtext('audit_chain'))"


# ---------------------------------------------------------------------------
# Hashing primitives
# ---------------------------------------------------------------------------


def _stable_hash(payload: Any) -> str:
    """SHA-256 over a stable JSON representation. Default=str handles UUIDs/datetimes."""
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _compute_chain_hash(previous_hash: str, inputs_hash: str) -> str:
    """sha256(previous_hash || inputs_hash) — the chain link."""
    return hashlib.sha256(
        (previous_hash + inputs_hash).encode("utf-8")
    ).hexdigest()


def _synth_inputs_hash_for_action(
    *,
    action: str,
    entity_type: Optional[str],
    entity_id: Optional[uuid.UUID],
    details: Optional[dict],
    user_id: Optional[uuid.UUID],
    ip_address: Optional[str],
) -> str:
    """Deterministic inputs_hash for generic ``log_action`` rows.

    ``log_clinical_decision`` already computes ``inputs_hash`` from its own
    enriched payload. ``log_action`` historically did not — we synthesize
    one from the persisted columns + details so the chain has a stable
    invariant per row.
    """
    payload = {
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": details or {},
        "user_id": user_id,
        "ip_address": ip_address,
    }
    return _stable_hash(payload)


# ---------------------------------------------------------------------------
# Chain head lookup
# ---------------------------------------------------------------------------


async def _acquire_chain_lock(db: AsyncSession) -> None:
    """Take the per-transaction advisory lock that guards the chain head.

    Released automatically at COMMIT/ROLLBACK by Postgres.
    """
    await db.execute(text(_ADVISORY_LOCK_SQL))


async def _current_chain_head(db: AsyncSession) -> str:
    """Return the chain_hash of the last persisted row, or GENESIS if empty.

    Caller MUST hold the advisory lock for the chain head to be stable.
    """
    result = await db.execute(
        select(AuditLog.chain_hash)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row if row else GENESIS_HASH


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


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
    Create a chained audit log entry. Flushes (does not commit) so the
    entry participates in the caller's transaction — but the advisory
    lock IS taken, so callers MUST commit (or roll back) promptly.

    Usage:
        await log_action(db, user_id=user.id, action="login",
                         ip_address=request.client.host)
    """
    enriched = dict(details or {})
    if "inputs_hash" not in enriched:
        enriched["inputs_hash"] = _synth_inputs_hash_for_action(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            user_id=user_id,
            ip_address=ip_address,
        )

    await _acquire_chain_lock(db)
    previous_hash = await _current_chain_head(db)
    chain_hash = _compute_chain_hash(previous_hash, enriched["inputs_hash"])

    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=enriched,
        ip_address=ip_address,
        previous_hash=previous_hash,
        chain_hash=chain_hash,
    )
    db.add(entry)
    await db.flush()
    return entry


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
    - ``model_version``: which agent + LLM produced this decision
    - ``inputs_hash``:   sha256 of the (details + model_version) payload,
      used as a tamper-evidence signal and as a dedup key.

    The row is also linked into the global hash chain via ``previous_hash``
    and ``chain_hash`` columns.

    ``entity_type`` is hardcoded to ``"case"`` since clinical decisions are
    scoped to a clinical case.
    """
    enriched = {**details, "model_version": model_version}
    enriched["inputs_hash"] = _stable_hash(enriched)

    await _acquire_chain_lock(db)
    previous_hash = await _current_chain_head(db)
    chain_hash = _compute_chain_hash(previous_hash, enriched["inputs_hash"])

    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type="case",
        entity_id=case_id,
        details=enriched,
        previous_hash=previous_hash,
        chain_hash=chain_hash,
    )
    db.add(entry)
    await db.flush()
    return entry


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def _recompute_inputs_hash_from_row(row: AuditLog) -> str:
    """Reverse-engineer the inputs_hash that SHOULD be stored for this row.

    Two formulas are in use, mirroring the two writers:

    * ``log_clinical_decision`` rows (heuristic: ``model_version`` is in
      ``details``): inputs_hash = sha256({**details_minus_inputs_hash}).
      ``model_version`` is part of ``details`` because the writer enriches
      details before hashing.

    * ``log_action`` rows: inputs_hash = sha256({action, entity_type,
      entity_id, details_minus_inputs_hash, user_id, ip_address}).
    """
    details = dict(row.details or {})
    details.pop("inputs_hash", None)

    if "model_version" in details:
        # Clinical decision formula
        return _stable_hash(details)

    # Generic log_action formula
    payload = {
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "details": details,
        "user_id": row.user_id,
        "ip_address": row.ip_address,
    }
    return _stable_hash(payload)


async def verify_chain(
    db: AsyncSession,
) -> tuple[bool, list[uuid.UUID]]:
    """Walk the entire audit_logs table and validate the chain.

    Returns:
        (True, [])               — chain is intact end-to-end.
        (False, [id, id, ...])   — list of broken row ids. A row is broken
                                   if any of:
            * ``previous_hash`` does not equal the prior row's ``chain_hash``
              (genesis row: ``previous_hash`` must equal ``"0"*64``)
            * stored ``inputs_hash`` does not match the hash recomputed
              from the row's actual content — content was mutated.
            * ``chain_hash`` does not equal sha256(previous_hash ||
              inputs_hash).

    Three independent checks make the chain robust against partial tamper:
    a row that mutates ``details`` but leaves ``inputs_hash`` untouched
    is caught by the first check; a row that ALSO updates ``inputs_hash``
    but does not propagate to ``chain_hash`` is caught by the third; a
    row that ALSO updates ``chain_hash`` will mismatch the next row's
    ``previous_hash`` and is caught at row N+1.

    Performance: single sequential scan over the table. Suitable for an
    admin endpoint and for CI smoke tests; for very large tables consider
    sampling or per-day windows.
    """
    result = await db.execute(
        select(AuditLog).order_by(
            AuditLog.created_at.asc(), AuditLog.id.asc()
        )
    )
    rows = result.scalars().all()

    broken: list[uuid.UUID] = []
    expected_prev = GENESIS_HASH

    for row in rows:
        # Check 1: previous_hash matches the running chain head.
        if row.previous_hash != expected_prev:
            broken.append(row.id)
            expected_prev = row.chain_hash
            continue

        details = row.details or {}
        stored_inputs_hash = details.get("inputs_hash")
        if stored_inputs_hash is None:
            broken.append(row.id)
            expected_prev = row.chain_hash
            continue

        # Check 2: stored inputs_hash matches recompute from row content.
        # Detects tampering of ``details``/columns without inputs_hash update.
        recomputed_inputs = _recompute_inputs_hash_from_row(row)
        if recomputed_inputs != stored_inputs_hash:
            broken.append(row.id)
            expected_prev = row.chain_hash
            continue

        # Check 3: chain_hash links via the recomputed inputs.
        recomputed_chain = _compute_chain_hash(
            row.previous_hash, stored_inputs_hash
        )
        if recomputed_chain != row.chain_hash:
            broken.append(row.id)
            expected_prev = row.chain_hash
            continue

        expected_prev = row.chain_hash

    return (len(broken) == 0, broken)
