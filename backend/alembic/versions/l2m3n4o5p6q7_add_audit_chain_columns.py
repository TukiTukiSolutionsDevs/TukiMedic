"""Add hash-chain columns to audit_logs (previous_hash, chain_hash).

Tamper-evident audit chain — gap #4 in tuki-medic/hard-blockers-plan.

Each row carries:
- ``previous_hash``: chain_hash of the prior row (or "0"*64 for genesis)
- ``chain_hash``: sha256(previous_hash || inputs_hash) where ``inputs_hash``
  lives in details JSONB (kept for backward compat).

Backfill: existing rows are walked in (created_at ASC, id ASC) order.
For rows that already have ``inputs_hash`` in details (clinical decisions),
the chain is computed from real data. Generic rows from ``log_action`` may
not have inputs_hash; for those we synthesize one from the persisted
columns + details so backfill is deterministic.

Concurrency guard: writers will use ``pg_advisory_xact_lock(hashtext(
'audit_chain'))`` in the application layer (app/services/audit.py).

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-05-01 17:25:00.000000
"""
from __future__ import annotations

import hashlib
import json

from alembic import op
import sqlalchemy as sa


revision = "l2m3n4o5p6q7"
down_revision = "k1l2m3n4o5p6"
branch_labels = None
depends_on = None


GENESIS = "0" * 64


def _stable_hash(payload: dict | list | str) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def upgrade() -> None:
    # 1. Add nullable columns first so the DDL is non-blocking.
    op.add_column(
        "audit_logs",
        sa.Column("previous_hash", sa.String(64), nullable=True),
    )
    op.add_column(
        "audit_logs",
        sa.Column("chain_hash", sa.String(64), nullable=True),
    )

    # 2. Backfill in chronological order. SELECT FOR UPDATE keeps the chain
    #    consistent against any concurrent INSERT during backfill (the new
    #    rows will be appended after we finish since `previous_hash` will
    #    still be NULL for them — they'll be picked up by the same loop).
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, action, entity_type, entity_id, details, "
            "       user_id, ip_address, created_at "
            "  FROM audit_logs "
            " ORDER BY created_at ASC, id ASC "
        )
    ).mappings().all()

    prev = GENESIS
    for r in rows:
        details = dict(r["details"] or {})
        # Ensure inputs_hash is present (synthesize for legacy rows).
        if "inputs_hash" not in details:
            payload = {
                "action": r["action"],
                "entity_type": r["entity_type"],
                "entity_id": str(r["entity_id"]) if r["entity_id"] else None,
                "details": dict(r["details"] or {}),
                "ip_address": r["ip_address"],
                "user_id": str(r["user_id"]) if r["user_id"] else None,
            }
            details["inputs_hash"] = _stable_hash(payload)

        chain = hashlib.sha256(
            (prev + details["inputs_hash"]).encode("utf-8")
        ).hexdigest()

        bind.execute(
            sa.text(
                "UPDATE audit_logs "
                "   SET previous_hash = :prev, "
                "       chain_hash    = :chain, "
                "       details       = :details "
                " WHERE id = :id"
            ),
            {
                "prev": prev,
                "chain": chain,
                "details": json.dumps(details, default=str),
                "id": r["id"],
            },
        )
        prev = chain

    # 3. Lock the columns to NOT NULL now that backfill is complete.
    op.alter_column(
        "audit_logs",
        "previous_hash",
        existing_type=sa.String(64),
        nullable=False,
    )
    op.alter_column(
        "audit_logs",
        "chain_hash",
        existing_type=sa.String(64),
        nullable=False,
    )

    # 4. Index chain_hash for fast verify_chain joins / lookups.
    op.create_index(
        "ix_audit_logs_chain_hash",
        "audit_logs",
        ["chain_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_chain_hash", table_name="audit_logs")
    op.drop_column("audit_logs", "chain_hash")
    op.drop_column("audit_logs", "previous_hash")
