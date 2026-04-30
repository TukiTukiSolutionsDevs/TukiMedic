"""LLM Router — resolves the active provider credential from the vault.

Multi-provider routing: queries provider_credentials, decrypts the stored
key, and returns a transient ProviderCredentialDTO.

Adding a new provider:
  1. Add an entry to _PROVIDER_CONFIGS with the correct base_url (or None).
  2. Add model names to PROVIDER_MODELS for "fast" and "smart" tiers.
  3. Register its credential via the admin vault API.
  4. Activate it.

Error mapping: NoActiveCredentialError → HTTP 503 (caller's responsibility).
"""
from __future__ import annotations

from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from sqlalchemy import select

from app.core.crypto import decrypt
from app.core.database import async_session
from app.models.provider_credential import ProviderCredential


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class NoActiveCredentialError(Exception):
    """No active credential exists for the requested provider.

    Callers should map this to HTTP 503 Service Unavailable.
    """


# ---------------------------------------------------------------------------
# Provider model tiers
# ---------------------------------------------------------------------------

#: Maps provider → tier → model name.
#: Agents request a tier ("fast" or "smart"); the router resolves the
#: provider-correct model name so no agent ever hardcodes a model string.
PROVIDER_MODELS: dict[str, dict[str, str]] = {
    "gemini": {
        "fast": "gemini-2.5-flash",
        "smart": "gemini-2.5-pro",
    },
    "openai": {
        "fast": "gpt-4o-mini",
        "smart": "gpt-4o",
    },
    "anthropic": {
        "fast": "claude-haiku-4-5",
        "smart": "claude-sonnet-4-5",
    },
}


# ---------------------------------------------------------------------------
# Provider config map
# ---------------------------------------------------------------------------


@dataclass
class _ProviderConfig:
    base_url: str | None = None


# Add new entries here as new providers are onboarded.
_PROVIDER_CONFIGS: dict[str, _ProviderConfig] = {
    "gemini": _ProviderConfig(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    ),
    "openai": _ProviderConfig(base_url=None),   # SDK default endpoint
    # "anthropic": _ProviderConfig(...)          # different client — wire later
}


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


@dataclass
class ProviderCredentialDTO:
    """Transient credential — decrypted api_key is NEVER persisted."""

    provider: str
    api_key: str        # decrypted; transient field — NOT stored in DB
    base_url: str | None = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_active_credential(provider: str = "gemini") -> ProviderCredentialDTO:
    """Return the decrypted active credential for *provider*.

    Queries ``provider_credentials``, decrypts the stored key via AES-GCM,
    and returns a transient ``ProviderCredentialDTO``.

    Args:
        provider: Provider name (e.g. ``"gemini"``, ``"openai"``).
            Defaults to ``"gemini"``.

    Returns:
        ``ProviderCredentialDTO`` with decrypted ``api_key`` and resolved
        ``base_url`` for the provider.

    Raises:
        NoActiveCredentialError: If no active credential exists for
            *provider*. Callers should map this to HTTP 503.
    """
    async with async_session() as db:
        result = await db.execute(
            select(ProviderCredential).where(
                ProviderCredential.provider == provider,
                ProviderCredential.is_active.is_(True),
            )
        )
        cred = result.scalar_one_or_none()

    if cred is None:
        raise NoActiveCredentialError(
            f"No active credential found for provider '{provider}'. "
            "Create and activate one via the admin credentials API "
            "(POST /admin/credentials → PATCH /admin/credentials/{id}/activate)."
        )

    api_key = decrypt(cred.encrypted_key, cred.iv, cred.tag).decode()
    cfg = _PROVIDER_CONFIGS.get(provider, _ProviderConfig())

    return ProviderCredentialDTO(
        provider=provider,
        api_key=api_key,
        base_url=cfg.base_url,
    )


def get_chat_model(
    tier: str,
    cred: "ProviderCredentialDTO",
    temperature: float = 0.0,
) -> ChatOpenAI:
    """Return a configured ChatOpenAI for *tier* and *cred*.

    Resolves the provider-correct model name from PROVIDER_MODELS so
    agent code never hardcodes a model string. Falls back to the openai
    tier map for unknown providers.

    Args:
        tier: ``"fast"`` or ``"smart"``.
        cred: Active provider credential from the vault.
        temperature: Sampling temperature (default 0.0 for determinism).

    Returns:
        ``ChatOpenAI`` instance configured with the correct model,
        api_key, base_url, and temperature for the provider.
    """
    tiers = PROVIDER_MODELS.get(cred.provider, PROVIDER_MODELS["openai"])
    model_name = tiers.get(tier, tiers["fast"])
    return ChatOpenAI(
        model=model_name,
        api_key=cred.api_key,
        base_url=cred.base_url,
        temperature=temperature,
    )
