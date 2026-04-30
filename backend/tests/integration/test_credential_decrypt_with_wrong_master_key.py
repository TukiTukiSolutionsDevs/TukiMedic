"""
Integration: decrypting a DB-stored credential with the wrong master key
must raise cryptography.exceptions.InvalidTag — never return garbage plaintext.

Simulates a 'vault restarted with wrong VAULT_MASTER_KEY' scenario by swapping
crypto._MASTER_KEY mid-test (same technique as test_key_vault.py unit test,
but against a real DB-persisted BYTEA blob instead of in-memory bytes).
"""
from __future__ import annotations

import uuid

import pytest
from cryptography.exceptions import InvalidTag
from sqlalchemy import select

import app.core.crypto as crypto_mod
from app.core.crypto import decrypt, encrypt
from app.models.provider_credential import ProviderCredential
from app.models.user import User


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def crypto_admin(db_session):
    """Minimal user for the created_by_user_id FK on provider_credentials."""
    from app.core.security import get_password_hash

    user = User(
        email=f"crypto_{uuid.uuid4().hex[:8]}@integration.example",
        password_hash=get_password_hash("crypto-test-pass-789!"),
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
async def test_decrypt_with_wrong_master_key_raises_invalid_tag(db_session, crypto_admin):
    """
    Storing a credential encrypted with key A then decrypting with key B raises
    InvalidTag — never silently returns garbage plaintext.

    Steps:
    1. Encrypt with the current (correct) master key.
    2. Persist the ciphertext blob to provider_credentials (BYTEA columns).
    3. Fetch back from DB (proves bytes survive PG round-trip intact).
    4. Swap crypto._MASTER_KEY to a wrong key.
    5. Assert decrypt raises InvalidTag.
    6. Restore the correct key and assert it still decrypts correctly.
    """
    api_key = b"sk-very-secret-credential-must-not-leak"

    # Step 1 & 2: encrypt and persist
    ciphertext, iv, tag = encrypt(api_key)
    cred = ProviderCredential(
        provider=f"wrongkey_{uuid.uuid4().hex[:6]}",
        label="wrong-master-key-test",
        encrypted_key=ciphertext,
        iv=iv,
        tag=tag,
        is_active=False,
        created_by_user_id=crypto_admin.id,
    )
    db_session.add(cred)
    await db_session.commit()

    # Step 3: fetch fresh from DB
    result = await db_session.execute(
        select(ProviderCredential).where(ProviderCredential.id == cred.id)
    )
    persisted = result.scalar_one()

    # Step 4-5: swap key and assert failure
    correct_key = crypto_mod._MASTER_KEY
    # Bitwise-flip every byte to guarantee a different valid-length key.
    wrong_key = bytes(b ^ 0xFF for b in correct_key)
    assert wrong_key != correct_key  # sanity

    try:
        crypto_mod._MASTER_KEY = wrong_key
        with pytest.raises(InvalidTag):
            decrypt(persisted.encrypted_key, persisted.iv, persisted.tag)
    finally:
        # Step 6: ALWAYS restore — other tests depend on the correct key.
        crypto_mod._MASTER_KEY = correct_key

    # Correct key must still work after restore
    recovered = decrypt(persisted.encrypted_key, persisted.iv, persisted.tag)
    assert recovered == api_key, (
        "Decryption with the correct key must succeed after restoring _MASTER_KEY"
    )


@pytest.mark.integration
async def test_partial_key_corruption_raises_invalid_tag(db_session, crypto_admin):
    """
    Even flipping a single bit of the master key must raise InvalidTag.

    AES-256-GCM's authentication tag covers the entire ciphertext; any key
    difference — however small — must fail authentication.
    """
    api_key = b"sk-partial-corruption-test-key"
    ciphertext, iv, tag = encrypt(api_key)

    cred = ProviderCredential(
        provider=f"partial_{uuid.uuid4().hex[:6]}",
        label="partial-corruption-test",
        encrypted_key=ciphertext,
        iv=iv,
        tag=tag,
        is_active=False,
        created_by_user_id=crypto_admin.id,
    )
    db_session.add(cred)
    await db_session.commit()

    result = await db_session.execute(
        select(ProviderCredential).where(ProviderCredential.id == cred.id)
    )
    persisted = result.scalar_one()

    correct_key = crypto_mod._MASTER_KEY
    # Flip only the last byte of the key
    one_bit_off = correct_key[:-1] + bytes([correct_key[-1] ^ 0x01])
    assert one_bit_off != correct_key

    try:
        crypto_mod._MASTER_KEY = one_bit_off
        with pytest.raises(InvalidTag):
            decrypt(persisted.encrypted_key, persisted.iv, persisted.tag)
    finally:
        crypto_mod._MASTER_KEY = correct_key
