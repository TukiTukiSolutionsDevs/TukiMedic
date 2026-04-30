"""TDD — S4.0.c-3,5: AES-GCM vault crypto (round-trip, tamper, wrong key, boot guard)."""
from __future__ import annotations

import importlib
import os
import sys

import pytest


# ---------------------------------------------------------------------------
# S4.0.c-3: Encryption round-trip
# ---------------------------------------------------------------------------


def test_encrypt_decrypt_round_trip():
    """Encrypting then decrypting returns the original bytes."""
    from app.core.crypto import decrypt, encrypt

    plaintext = b"sk-super-secret-api-key-123456"
    ciphertext, iv, tag = encrypt(plaintext)
    recovered = decrypt(ciphertext, iv, tag)
    assert recovered == plaintext


def test_encrypt_produces_unique_iv_per_call():
    """Each encryption call uses a fresh random IV — GCM nonce must never repeat."""
    from app.core.crypto import encrypt

    _, iv1, _ = encrypt(b"same-payload")
    _, iv2, _ = encrypt(b"same-payload")
    assert iv1 != iv2


def test_encrypt_iv_is_12_bytes():
    """AES-GCM standard: 96-bit (12-byte) IV."""
    from app.core.crypto import encrypt

    _, iv, _ = encrypt(b"test")
    assert len(iv) == 12


def test_encrypt_tag_is_16_bytes():
    """GCM authentication tag is 128 bits (16 bytes)."""
    from app.core.crypto import encrypt

    _, _, tag = encrypt(b"test")
    assert len(tag) == 16


def test_plaintext_not_in_ciphertext():
    """Ciphertext must not contain plaintext in clear."""
    from app.core.crypto import encrypt

    plaintext = b"verysecretapikey"
    ciphertext, _, _ = encrypt(plaintext)
    assert plaintext not in ciphertext


# ---------------------------------------------------------------------------
# S4.0.c-3: Decrypt with tampered data raises InvalidTag
# ---------------------------------------------------------------------------


def test_decrypt_tampered_ciphertext_raises():
    """AES-GCM integrity: tampered ciphertext raises InvalidTag."""
    from cryptography.exceptions import InvalidTag

    from app.core.crypto import decrypt, encrypt

    plaintext = b"do-not-tamper"
    ciphertext, iv, tag = encrypt(plaintext)
    tampered = bytes([ciphertext[0] ^ 0xFF]) + ciphertext[1:]
    with pytest.raises(InvalidTag):
        decrypt(tampered, iv, tag)


def test_decrypt_tampered_tag_raises():
    """AES-GCM integrity: tampered tag raises InvalidTag."""
    from cryptography.exceptions import InvalidTag

    from app.core.crypto import decrypt, encrypt

    plaintext = b"legit-payload"
    ciphertext, iv, tag = encrypt(plaintext)
    bad_tag = bytes([tag[0] ^ 0xFF]) + tag[1:]
    with pytest.raises(InvalidTag):
        decrypt(ciphertext, iv, bad_tag)


def test_decrypt_tampered_iv_raises():
    """AES-GCM integrity: wrong IV raises InvalidTag."""
    from cryptography.exceptions import InvalidTag

    from app.core.crypto import decrypt, encrypt

    plaintext = b"another-test"
    ciphertext, iv, tag = encrypt(plaintext)
    bad_iv = bytes([iv[0] ^ 0xFF]) + iv[1:]
    with pytest.raises(InvalidTag):
        decrypt(ciphertext, bad_iv, tag)


# ---------------------------------------------------------------------------
# S4.0.c-3: Decrypt with wrong master key raises — no silent fallback
# ---------------------------------------------------------------------------


def test_decrypt_wrong_master_key_raises():
    """Using a different AES key raises InvalidTag — no silent fallback."""
    from cryptography.exceptions import InvalidTag

    import app.core.crypto as crypto

    plaintext = b"key-rotation-test"
    ciphertext, iv, tag = crypto.encrypt(plaintext)

    original_key = crypto._MASTER_KEY
    crypto._MASTER_KEY = os.urandom(32)  # swap in a different 32-byte key
    try:
        with pytest.raises(InvalidTag):
            crypto.decrypt(ciphertext, iv, tag)
    finally:
        crypto._MASTER_KEY = original_key  # always restore


# ---------------------------------------------------------------------------
# S4.0.c-5: Missing VAULT_MASTER_KEY fails at import
# ---------------------------------------------------------------------------


def test_missing_vault_master_key_fails_at_import():
    """Importing app.core.crypto without VAULT_MASTER_KEY raises RuntimeError."""
    # Save current module state
    saved_module = sys.modules.pop("app.core.crypto", None)
    saved_key = os.environ.pop("VAULT_MASTER_KEY", None)
    try:
        with pytest.raises(RuntimeError, match="VAULT_MASTER_KEY"):
            importlib.import_module("app.core.crypto")
    finally:
        # Clean any partial failed import
        sys.modules.pop("app.core.crypto", None)
        # Restore env var
        if saved_key is not None:
            os.environ["VAULT_MASTER_KEY"] = saved_key
        # Restore original (correctly-loaded) module
        if saved_module is not None:
            sys.modules["app.core.crypto"] = saved_module
