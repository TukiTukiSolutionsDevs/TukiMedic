"""
Opt-in live-LLM smoke tests.

These tests are SKIPPED by default. Enable with:
    poetry run pytest tests/test_live_llm.py --live-llm
or
    RUN_LIVE_LLM=1 poetry run pytest tests/test_live_llm.py

They require a running OpenAI-compatible endpoint. Default points at the
Meridian Shim at http://localhost:4568/v1, which serves Anthropic Claude
models with no per-token cost (uses the developer's Claude subscription).

Override via env:
    LIVE_LLM_BASE_URL  (default http://localhost:4568/v1)
    LIVE_LLM_MODEL     (default claude-haiku-4-5-20251001)
    LIVE_LLM_API_KEY   (default sk-dummy)
"""
from __future__ import annotations

import os

import pytest
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.agents._llm_safe import safe_ainvoke


pytestmark = pytest.mark.live_llm


def _llm():
    base_url = os.environ.get("LIVE_LLM_BASE_URL", "http://localhost:4568/v1")
    model = os.environ.get("LIVE_LLM_MODEL", "claude-haiku-4-5-20251001")
    api_key = os.environ.get("LIVE_LLM_API_KEY", "sk-dummy")
    return ChatOpenAI(model=model, base_url=base_url, api_key=api_key, temperature=0.0)


class TriageJudgement(BaseModel):
    urgency: str = Field(description="One of 'low', 'medium', 'high'")
    rationale: str = Field(description="Short reason in Spanish")


@pytest.mark.asyncio
async def test_meridian_chat_completion_round_trip():
    """Plain chat: server speaks OpenAI-compatible, returns Spanish text."""
    llm = _llm()
    resp = await llm.ainvoke(
        [
            {"role": "system", "content": "Respondé brevemente en español."},
            {"role": "user", "content": "Decime una palabra de saludo."},
        ]
    )
    assert resp.content
    assert isinstance(resp.content, str)


@pytest.mark.xfail(
    reason=(
        "Meridian shim's OpenAI→Anthropic translation does not currently "
        "preserve LangChain's default with_structured_output() (function "
        "calling) shape. PRODUCTION RISK: every agent uses with_structured_output. "
        "Either patch the shim to translate function_call → tool_use, or set "
        "method='json_mode' on the agents and have them parse JSON from text. "
        "Tracked under Sprint 2 follow-up."
    ),
    strict=False,
)
@pytest.mark.asyncio
async def test_meridian_structured_output_smoke():
    """Structured output works — agents rely on this contract."""
    llm = _llm().with_structured_output(TriageJudgement)
    judgement: TriageJudgement = await llm.ainvoke(
        [
            {
                "role": "system",
                "content": (
                    "Sos un médico de triage. Clasificá la consulta del paciente. "
                    "Devolvé únicamente JSON estructurado."
                ),
            },
            {"role": "user", "content": "Tengo dolor de cabeza leve hace 1 día."},
        ]
    )
    assert judgement.urgency in {"low", "medium", "high"}
    assert judgement.rationale


@pytest.mark.asyncio
async def test_safe_ainvoke_returns_real_result_with_live_endpoint():
    """The safe_ainvoke helper should pass through real responses, not the fallback."""
    fallback = "FALLBACK"
    out = await safe_ainvoke(
        _llm(),
        [{"role": "user", "content": "Decí 'pong' y nada más."}],
        fallback=fallback,
        agent_name="live-smoke",
    )
    assert out is not fallback
    # Real returns are LangChain message objects with .content
    assert getattr(out, "content", "") != ""
