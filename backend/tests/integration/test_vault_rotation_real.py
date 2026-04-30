"""
Integration: provider credential encryption, rotation, and single-active invariant.

Uses the real DB (session-scoped container) to prove:
1. Encrypt → persist → retrieve → decrypt round-trip works end-to-end.
2. Rotation produces different ciphertext; old plaintext is not accessible via new blob.
3. The partial unique index on (provider) WHERE is_active=true actually fires,
   raising IntegrityError when two active credentials exist for the same provider.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.crypto import decrypt, encrypt
from app.models.provider_credential import ProviderCredential
from app.models.user import User


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def vault_admin(db_session):
    """Admin user needed for provider_credentials.created_by_user_id FK."""
    from app.core.security import get_password_hash

    user = User(
        email=f"vault_admin_{uuid.uuid4().hex[:8]}@integration.example",
        password_hash=get_password_hash("vault-test-pass-456!"),
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_credential_encrypt_persist_decrypt_round_trip(db_session, vault_admin):
    """
    Encrypt an API key, persist to DB, fetch fresh, decrypt — must equal original.

    Proves the full AES-256-GCM round-trip survives PostgreSQL BYTEA storage.
    """
    plaintext = b"sk-integration-round-trip-key-abc123"
    ciphertext, iv, tag = encrypt(plaintext)

    cred = ProviderCredential(
        provider=f"openai_{uuid.uuid4().hex[:6]}",
        label="round-trip-test",
        encrypted_key=ciphertext,
        iv=iv,
        tag=tag,
        is_active=False,
        created_by_user_id=vault_admin.id,
    )
    db_session.add(cred)
    await db_session.commit()

    result = await db_session.execute(
        select(ProviderCredential).where(ProviderCredential.id == cred.id)
    )
    persisted = result.scalar_one()

    recovered = decrypt(persisted.encrypted_key, persisted.iv, persisted.tag)
    assert recovered == plaintext, (
        "Decrypted key must equal original plaintext after PostgreSQL BYTEA round-trip"
    )


@pytest.mark.integration
async def test_credential_rotation_replaces_ciphertext(db_session, vault_admin):
    """
    After rotation the encrypted_key, iv, and tag must all change.
    New ciphertext must decrypt to new key; old plaintext must NOT come out.
    """
    original_key = b"sk-original-before-rotation-xyz"
    c1, iv1, t1 = encrypt(original_key)

    cred = ProviderCredential(
        provider=f"anthropic_{uuid.uuid4().hex[:6]}",
        label="rotation-test",
        encrypted_key=c1,
        iv=iv1,
        tag=t1,
        is_active=False,
        created_by_user_id=vault_admin.id,
    )
    db_session.add(cred)
    await db_session.commit()

    # Rotate: encrypt a new key, update the DB record
    new_key = b"sk-rotated-new-key-after-rotation"
    c2, iv2, t2 = encrypt(new_key)

    cred.encrypted_key = c2
    cred.iv = iv2
    cred.tag = t2
    cred.rotated_at = datetime.now(timezone.utc)
    await db_session.commit()

    result = await db_session.execute(
        select(ProviderCredential).where(ProviderCredential.id == cred.id)
    )
    rotated = result.scalar_one()

    # Blob must differ
    assert rotated.encrypted_key != c1, "encrypted_key must change after rotation"
    assert rotated.iv != iv1, "iv must change after rotation (fresh nonce per encrypt call)"
    assert rotated.rotated_at is not None, "rotated_at must be set"

    # New blob decrypts to new key only
    recovered = decrypt(rotated.encrypted_key, rotated.iv, rotated.tag)
    assert recovered == new_key, "New ciphertext must decrypt to the new key"
    assert recovered != original_key, "New ciphertext must NOT decrypt to old key"


@pytest.mark.integration
async def test_single_active_invariant_enforced_by_partial_index(db_session, vault_admin):
    """
    Inserting a second active credential for the same provider must raise IntegrityError.

    This proves the partial unique index on (provider) WHERE is_active=true
    actually fires at the DB level — not just application-level logic.
    """
    provider = f"gemini_{uuid.uuid4().hex[:8]}"  # unique per test run

    # First active credential — must succeed
    c1, iv1, t1 = encrypt(b"sk-gemini-primary-active")
    cred1 = ProviderCredential(
        provider=provider,
        label="primary",
        encrypted_key=c1,
        iv=iv1,
        tag=t1,
        is_active=True,
        created_by_user_id=vault_admin.id,
    )
    db_session.add(cred1)
    await db_session.commit()

    # Second active credential for same provider — must violate index
    c2, iv2, t2 = encrypt(b"sk-gemini-duplicate-active")
    cred2 = ProviderCredential(
        provider=provider,
        label="duplicate-active",
        encrypted_key=c2,
        iv=iv2,
        tag=t2,
        is_active=True,  # violates partial unique index
        created_by_user_id=vault_admin.id,
    )
    db_session.add(cred2)

    with pytest.raises(IntegrityError):
        await db_session.flush()

    # Rollback so the session is usable for teardown
    await db_session.rollback()
