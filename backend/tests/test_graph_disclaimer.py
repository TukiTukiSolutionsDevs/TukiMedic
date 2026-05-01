"""
Tests for disclaimer enforcement at the synthesizer node level (graph.py).

Strict TDD — RED first: these tests define the contract BEFORE the fix.
The _with_disclaimer wrapper must:
  1. Append BASE_DISCLAIMER when the synthesizer returns a response without it.
  2. NOT duplicate it when the synthesizer already included it (idempotent).
"""
import pytest
from unittest.mock import AsyncMock

from app.orchestrator.graph import _with_disclaimer
from app.agents.synthesizer.agent import BASE_DISCLAIMER, DISCLAIMER_SEPARATOR


@pytest.mark.asyncio
async def test_node_appends_base_disclaimer_when_missing():
    """Node must append BASE_DISCLAIMER when synthesizer omits it."""
    inner = AsyncMock(
        return_value={
            "synthesized_response": "Tomá descanso e hidratación.",
            "attention_level": "rutina",
            "current_node": "synthesizer",
        }
    )
    node = _with_disclaimer(inner)
    result = await node({})
    assert BASE_DISCLAIMER in result["synthesized_response"], (
        f"BASE_DISCLAIMER missing from: {result['synthesized_response']!r}"
    )
    assert "Tomá descanso e hidratación." in result["synthesized_response"]


@pytest.mark.asyncio
async def test_node_does_not_duplicate_disclaimer_when_present():
    """If BASE_DISCLAIMER is already in the response, node must not add it again."""
    response = f"Tomá descanso.{DISCLAIMER_SEPARATOR}{BASE_DISCLAIMER}"
    inner = AsyncMock(
        return_value={
            "synthesized_response": response,
            "attention_level": "rutina",
            "current_node": "synthesizer",
        }
    )
    node = _with_disclaimer(inner)
    result = await node({})
    count = result["synthesized_response"].count(BASE_DISCLAIMER)
    assert count == 1, f"Expected exactly 1 disclaimer, found {count}"


@pytest.mark.asyncio
async def test_node_appends_when_llm_paraphrase_present():
    """LLM-generated paraphrase does NOT satisfy the BASE_DISCLAIMER check — node must still append."""
    paraphrase = "Esta es una guía informativa. Consultá con tu médico."
    inner = AsyncMock(
        return_value={
            "synthesized_response": f"Hidratate bien.\n\n---\n\n{paraphrase}",
            "attention_level": "24-48h",
            "current_node": "synthesizer",
        }
    )
    node = _with_disclaimer(inner)
    result = await node({})
    assert BASE_DISCLAIMER in result["synthesized_response"], (
        "BASE_DISCLAIMER must be appended even when LLM disclaimer paraphrase is present"
    )


@pytest.mark.asyncio
async def test_node_preserves_other_result_keys():
    """_with_disclaimer must not drop any keys returned by the inner node."""
    inner = AsyncMock(
        return_value={
            "synthesized_response": "Sin disclaimer.",
            "attention_level": "hoy",
            "current_node": "synthesizer",
        }
    )
    node = _with_disclaimer(inner)
    result = await node({"case_id": "x"})
    assert result["attention_level"] == "hoy"
    assert result["current_node"] == "synthesizer"
