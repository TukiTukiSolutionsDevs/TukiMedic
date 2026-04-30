"""
Tests — BUG 1: PROVIDER_MODELS and get_chat_model.

RED phase: these tests fail until llm_router.py exposes PROVIDER_MODELS and get_chat_model.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.llm_router import ProviderCredentialDTO


def _gemini_cred(api_key: str = "sk-test") -> ProviderCredentialDTO:
    return ProviderCredentialDTO(
        provider="gemini",
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )


def _openai_cred(api_key: str = "sk-test") -> ProviderCredentialDTO:
    return ProviderCredentialDTO(provider="openai", api_key=api_key, base_url=None)


# ---------------------------------------------------------------------------
# PROVIDER_MODELS constant
# ---------------------------------------------------------------------------


class TestProviderModels:
    def test_provider_models_exists(self):
        from app.services.llm_router import PROVIDER_MODELS
        assert PROVIDER_MODELS is not None

    def test_gemini_fast_is_gemini_flash(self):
        from app.services.llm_router import PROVIDER_MODELS
        assert PROVIDER_MODELS["gemini"]["fast"] == "gemini-2.5-flash"

    def test_gemini_smart_is_gemini_pro(self):
        from app.services.llm_router import PROVIDER_MODELS
        assert PROVIDER_MODELS["gemini"]["smart"] == "gemini-2.5-pro"

    def test_openai_fast_is_gpt4o_mini(self):
        from app.services.llm_router import PROVIDER_MODELS
        assert PROVIDER_MODELS["openai"]["fast"] == "gpt-4o-mini"

    def test_openai_smart_is_gpt4o(self):
        from app.services.llm_router import PROVIDER_MODELS
        assert PROVIDER_MODELS["openai"]["smart"] == "gpt-4o"

    def test_gemini_has_both_tiers(self):
        from app.services.llm_router import PROVIDER_MODELS
        assert {"fast", "smart"}.issubset(PROVIDER_MODELS["gemini"])

    def test_openai_has_both_tiers(self):
        from app.services.llm_router import PROVIDER_MODELS
        assert {"fast", "smart"}.issubset(PROVIDER_MODELS["openai"])


# ---------------------------------------------------------------------------
# get_chat_model function
# ---------------------------------------------------------------------------


class TestGetChatModel:
    def test_function_exists(self):
        from app.services.llm_router import get_chat_model
        assert callable(get_chat_model)

    def test_gemini_fast_resolves_to_flash(self):
        from app.services.llm_router import get_chat_model
        with patch("app.services.llm_router.ChatOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            get_chat_model("fast", _gemini_cred())
        assert mock_cls.call_args.kwargs["model"] == "gemini-2.5-flash"

    def test_gemini_smart_resolves_to_pro(self):
        from app.services.llm_router import get_chat_model
        with patch("app.services.llm_router.ChatOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            get_chat_model("smart", _gemini_cred())
        assert mock_cls.call_args.kwargs["model"] == "gemini-2.5-pro"

    def test_gemini_model_is_never_gpt4o(self):
        """CRITICAL: Gemini provider must never receive gpt-4o as model name."""
        from app.services.llm_router import get_chat_model
        with patch("app.services.llm_router.ChatOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            get_chat_model("fast", _gemini_cred())
        assert "gpt-4o" not in mock_cls.call_args.kwargs["model"]

    def test_openai_fast_resolves_to_mini(self):
        from app.services.llm_router import get_chat_model
        with patch("app.services.llm_router.ChatOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            get_chat_model("fast", _openai_cred())
        assert mock_cls.call_args.kwargs["model"] == "gpt-4o-mini"

    def test_openai_smart_resolves_to_gpt4o(self):
        from app.services.llm_router import get_chat_model
        with patch("app.services.llm_router.ChatOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            get_chat_model("smart", _openai_cred())
        assert mock_cls.call_args.kwargs["model"] == "gpt-4o"

    def test_api_key_forwarded(self):
        from app.services.llm_router import get_chat_model
        with patch("app.services.llm_router.ChatOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            get_chat_model("fast", _gemini_cred(api_key="sk-vault-xyz"))
        assert mock_cls.call_args.kwargs["api_key"] == "sk-vault-xyz"

    def test_gemini_base_url_forwarded(self):
        from app.services.llm_router import get_chat_model
        cred = _gemini_cred()
        with patch("app.services.llm_router.ChatOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            get_chat_model("fast", cred)
        assert mock_cls.call_args.kwargs["base_url"] == cred.base_url

    def test_temperature_forwarded(self):
        from app.services.llm_router import get_chat_model
        with patch("app.services.llm_router.ChatOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            get_chat_model("fast", _gemini_cred(), temperature=0.7)
        assert mock_cls.call_args.kwargs["temperature"] == 0.7

    def test_default_temperature_is_zero(self):
        from app.services.llm_router import get_chat_model
        with patch("app.services.llm_router.ChatOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            get_chat_model("fast", _gemini_cred())
        assert mock_cls.call_args.kwargs["temperature"] == 0.0

    def test_returns_chat_openai_instance(self):
        from app.services.llm_router import get_chat_model
        with patch("app.services.llm_router.ChatOpenAI") as mock_cls:
            expected = MagicMock()
            mock_cls.return_value = expected
            result = get_chat_model("fast", _gemini_cred())
        assert result is expected
