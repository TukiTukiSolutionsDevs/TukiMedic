"""TDD — S4.0.d-1: LLM router service.

RED phase: llm_router.py does not exist yet — imports will fail.

Tests:
- get_active_credential("gemini") returns ProviderCredentialDTO with decrypted key
- get_active_credential("gemini") raises NoActiveCredentialError when no active row
- Gemini provider config carries the correct OpenAI-compat base_url
- OpenAI provider has no base_url override
- Live Gemini integration (skipped unless --live-llm / LIVE_LLM=1)
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm_router import (
    NoActiveCredentialError,
    ProviderCredentialDTO,
    get_active_credential,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_active_cred(api_key_plaintext: str = "my-secret-key", provider: str = "gemini"):
    """Build a mock ProviderCredential with real AES-GCM encrypted bytes."""
    from app.core.crypto import encrypt

    ciphertext, iv, tag = encrypt(api_key_plaintext.encode())
    cred = MagicMock()
    cred.provider = provider
    cred.encrypted_key = ciphertext
    cred.iv = iv
    cred.tag = tag
    cred.is_active = True
    return cred


def _db_patch(cred_or_none):
    """Patch async_session so scalar_one_or_none() returns cred_or_none."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = cred_or_none

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    return patch("app.services.llm_router.async_session", MagicMock(return_value=mock_cm))


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestGetActiveCredential:
    @pytest.mark.asyncio
    async def test_returns_dto_with_decrypted_key(self):
        """Active credential → ProviderCredentialDTO with plaintext api_key."""
        plaintext = "sk-gemini-test-key-abc123"
        mock_cred = _make_active_cred(api_key_plaintext=plaintext, provider="gemini")

        with _db_patch(mock_cred):
            dto = await get_active_credential("gemini")

        assert isinstance(dto, ProviderCredentialDTO)
        assert dto.api_key == plaintext
        assert dto.provider == "gemini"

    @pytest.mark.asyncio
    async def test_gemini_has_correct_base_url(self):
        """Gemini provider config carries the OpenAI-compatible base URL."""
        mock_cred = _make_active_cred(provider="gemini")

        with _db_patch(mock_cred):
            dto = await get_active_credential("gemini")

        assert dto.base_url == "https://generativelanguage.googleapis.com/v1beta/openai/"

    @pytest.mark.asyncio
    async def test_raises_no_active_credential_error_when_none(self):
        """No active credential → NoActiveCredentialError (maps to HTTP 503)."""
        with _db_patch(None):
            with pytest.raises(NoActiveCredentialError):
                await get_active_credential("gemini")

    @pytest.mark.asyncio
    async def test_error_message_mentions_provider(self):
        """Error message must name the requested provider for debuggability."""
        with _db_patch(None):
            with pytest.raises(NoActiveCredentialError, match="gemini"):
                await get_active_credential("gemini")

    @pytest.mark.asyncio
    async def test_openai_provider_has_no_base_url(self):
        """OpenAI provider uses the SDK default endpoint — no base_url override."""
        mock_cred = _make_active_cred(provider="openai")

        with _db_patch(mock_cred):
            dto = await get_active_credential("openai")

        assert dto.base_url is None

    @pytest.mark.asyncio
    async def test_dto_provider_field_matches_argument(self):
        """DTO.provider reflects the requested provider name."""
        mock_cred = _make_active_cred(provider="gemini")

        with _db_patch(mock_cred):
            dto = await get_active_credential("gemini")

        assert dto.provider == "gemini"

    @pytest.mark.asyncio
    async def test_api_key_is_transient_not_db_field(self):
        """Decrypted api_key comes from decrypt(), not from a stored plaintext field."""
        plaintext = "transient-key-xyz"
        mock_cred = _make_active_cred(api_key_plaintext=plaintext)

        with _db_patch(mock_cred):
            dto = await get_active_credential("gemini")

        assert dto.api_key == plaintext
        # Confirm it does NOT equal the raw encrypted bytes
        assert dto.api_key != mock_cred.encrypted_key


# ---------------------------------------------------------------------------
# Live integration test (skipped unless --live-llm / LIVE_LLM=1)
# ---------------------------------------------------------------------------


@pytest.mark.live_llm
class TestGeminiLiveIntegration:
    @pytest.mark.asyncio
    async def test_live_get_active_gemini_credential(self):
        """Requires a real active gemini credential in the DB.

        Enable with: LIVE_LLM=1 poetry run pytest -m live_llm
        """
        dto = await get_active_credential("gemini")
        assert dto.api_key  # non-empty string
        assert dto.base_url == "https://generativelanguage.googleapis.com/v1beta/openai/"
        assert dto.provider == "gemini"
