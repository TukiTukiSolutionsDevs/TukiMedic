"""TDD — Synthesizer clamps attention_level by triage_level.

Surfaced by clinical eval baseline (commit 5f2a716): cardio-002 + gyneco-001
were yellow-triage cases that ended with attention_level="urgencia" via the
synthesizer node (NOT the escalation_node — current_node was 'guardrail').

Root cause: synthesizer prompt rule "Si hay desacuerdo entre especialistas,
usá el criterio más conservador (más urgente)" pushes the LLM toward
urgencia whenever specialists raise differentials. The LLM cannot be trusted
to respect a categorical contract derived from triage_level.

Defensive fix: post-process the SynthesizedResponse and CLAMP
attention_level by the triage_level ceiling. Never escalate beyond what
triage said, but allow one notch of conservatism.
"""
from __future__ import annotations

from app.agents.synthesizer.agent import _clamp_attention


def test_yellow_caps_at_hoy_when_llm_picks_urgencia():
    assert _clamp_attention("yellow", "urgencia") == "hoy"


def test_yellow_keeps_hoy():
    assert _clamp_attention("yellow", "hoy") == "hoy"


def test_yellow_keeps_24_48h():
    assert _clamp_attention("yellow", "24-48h") == "24-48h"


def test_yellow_does_not_upgrade_rutina():
    """If LLM picks rutina for a yellow, preserve (no upward clamp)."""
    assert _clamp_attention("yellow", "rutina") == "rutina"


def test_green_caps_at_24_48h_when_llm_picks_urgencia():
    assert _clamp_attention("green", "urgencia") == "24-48h"


def test_green_caps_at_24_48h_when_llm_picks_hoy():
    assert _clamp_attention("green", "hoy") == "24-48h"


def test_green_keeps_rutina():
    assert _clamp_attention("green", "rutina") == "rutina"


def test_red_keeps_urgencia_no_cap():
    """Red triage allows urgencia — no clamping needed."""
    assert _clamp_attention("red", "urgencia") == "urgencia"


def test_unknown_triage_passes_through():
    """If triage_level is missing, don't clamp — preserve LLM choice."""
    assert _clamp_attention(None, "urgencia") == "urgencia"
    assert _clamp_attention(None, "hoy") == "hoy"
