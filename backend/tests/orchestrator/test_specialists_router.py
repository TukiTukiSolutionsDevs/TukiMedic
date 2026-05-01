"""TDD — Bypass medical_board for green-triage cases (latency optimization).

Background
----------
Clinical eval baseline showed P95 latency = 173.7s. Profile of the sequential
graph chain identified medical_board as a ~30-40s smart-tier LLM call that
adds little value for green-triage cases (low stakes, low diagnostic
ambiguity). Red cases never reach this point (triage_router escalates them
directly), so only yellow + green cases pay this cost.

The optimization adds a conditional edge after `specialists` that routes
green cases straight to `synthesizer`, bypassing `medical_board`. Yellow
cases keep the existing path through deliberation.
"""
from __future__ import annotations

from app.orchestrator.graph import _specialists_router


def test_green_triage_bypasses_medical_board():
    """Green cases skip the medical board for latency."""
    state = {"triage_level": "green", "specialist_outputs": {"medicina_general": {}}}
    assert _specialists_router(state) == "synthesizer"


def test_yellow_triage_goes_to_medical_board():
    """Yellow cases keep the deliberation path."""
    state = {"triage_level": "yellow", "specialist_outputs": {"cardiologia": {}}}
    assert _specialists_router(state) == "medical_board"


def test_unknown_triage_defaults_to_medical_board():
    """If triage_level somehow ends up missing, default to safer (longer) path."""
    state = {"specialist_outputs": {}}
    assert _specialists_router(state) == "medical_board"


def test_red_triage_would_go_to_medical_board_if_reached():
    """Red triages should not reach this router (triage_router escalates first),
    but if they ever do, route to medical_board for full deliberation."""
    state = {"triage_level": "red"}
    assert _specialists_router(state) == "medical_board"
