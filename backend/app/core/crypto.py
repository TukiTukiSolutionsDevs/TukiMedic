"""AES-256-GCM symmetric encryption for at-rest secret storage.

Master key is loaded from the VAULT_MASTER_KEY environment variable (base64,
must decode to exactly 32 bytes). Fails at module import if the variable is
absent or malformed — the application should not start with a misconfigured
vault.

Generate a master key:
    python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
"""
from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ---------------------------------------------------------------------------
# Master-key bootstrap — fail fast if env is missing or malformed.
# ---------------------------------------------------------------------------


def _load_master_key() -> bytes:
    raw = os.environ.get("VAULT_MASTER_KEY", "")
    if not raw:
        raise RuntimeError(
            "VAULT_MASTER_KEY env var is required but not set. "
            "Generate one with: "
            'python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"'
        )
    try:
        key = base64.b64decode(raw)
    except Exception as exc:
        raise RuntimeError(
            f"VAULT_MASTER_KEY is not valid base64: {exc}"
        ) from exc
    if len(key) != 32:
        raise RuntimeError(
            f"VAULT_MASTER_KEY must decode to exactly 32 bytes (AES-256); "
            f"got {len(key)}. Re-generate with: "
            'python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"'
        )
    return key


# Loaded once at module import — application fails fast on misconfiguration.
_MASTER_KEY: bytes = _load_master_key()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def encrypt(plaintext: bytes) -> tuple[bytes, bytes, bytes]:
    """Encrypt *plaintext* with AES-256-GCM.

    A fresh 12-byte IV is generated per call (GCM standard recommendation).

    Returns:
        (ciphertext, iv, tag)
        ciphertext — encrypted payload bytes.
        iv         — 12-byte random nonce; store alongside ciphertext.
        tag        — 16-byte authentication tag; store alongside ciphertext.
    """
    iv = os.urandom(12)  # 96-bit random nonce — unique per encryption
    aesgcm = AESGCM(_MASTER_KEY)
    # AESGCM.encrypt returns ciphertext || tag (tag is the last 16 bytes)
    ct_and_tag = aesgcm.encrypt(iv, plaintext, None)
    ciphertext = ct_and_tag[:-16]
    tag = ct_and_tag[-16:]
    return ciphertext, iv, tag


def decrypt(ciphertext: bytes, iv: bytes, tag: bytes) -> bytes:
    """Decrypt AES-256-GCM *ciphertext*.

    Raises:
        cryptography.exceptions.InvalidTag — if the ciphertext is tampered
        or the wrong master key is used. There is no silent fallback.
    """
    aesgcm = AESGCM(_MASTER_KEY)
    ct_and_tag = ciphertext + tag
    return aesgcm.decrypt(iv, ct_and_tag, None)
