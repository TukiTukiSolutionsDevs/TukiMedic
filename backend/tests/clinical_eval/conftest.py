"""
Clinical Evaluation Suite — conftest.py

Opt-in real-LLM evaluation layer. Runs 25 patient scenarios through the full
MedAgent graph (Triage → Specialists → Synthesizer) against the real Gemini
credential stored in the dev DB vault.

Enable:
    RUN_CLINICAL_EVAL=1 cd backend && poetry run pytest -m clinical_eval -v

Requirements:
    - Docker stack running (postgres on :5433)
    - Active Gemini credential in the dev DB vault
    - VAULT_MASTER_KEY in backend/.env matches the encryption key used for that credential
"""
from __future__ import annotations

import asyncio
import base64
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Load real .env BEFORE any app.* import.
# The global tests/conftest.py randomises VAULT_MASTER_KEY at module-load time;
# we re-load the real .env here so os.environ has the correct value when we
# need to decode the actual base64 key bytes below.
# ---------------------------------------------------------------------------
from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).parent.parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE, override=True)

import pytest  # noqa: E402


# ---------------------------------------------------------------------------
# Marker + skip logic
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "clinical_eval: end-to-end LLM eval — real Gemini, 25 scenarios "
        "(enable with RUN_CLINICAL_EVAL=1)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list) -> None:
    run_eval = os.environ.get("RUN_CLINICAL_EVAL") == "1"
    skip_marker = pytest.mark.skip(
        reason="clinical_eval: set RUN_CLINICAL_EVAL=1 to enable"
    )
    for item in items:
        if "clinical_eval" in item.keywords and not run_eval:
            item.add_marker(skip_marker)


# ---------------------------------------------------------------------------
# Gemini credential — fetched once per session from the dev DB vault.
# We briefly patch app.core.crypto._MASTER_KEY with the REAL vault key just
# for the credential fetch, then restore the value so the rest of the test
# session is unaffected.
# ---------------------------------------------------------------------------


async def _fetch_gemini_cred():
    from app.services.llm_router import get_active_credential

    return await get_active_credential("gemini")


@pytest.fixture(scope="session")
def gemini_cred():
    """Decrypted Gemini ProviderCredentialDTO from the dev DB vault.

    Skips the whole suite if:
      - RUN_CLINICAL_EVAL is not set
      - VAULT_MASTER_KEY is missing or invalid
      - docker postgres is unreachable
      - no active Gemini credential is registered
    """
    if os.environ.get("RUN_CLINICAL_EVAL") != "1":
        pytest.skip("RUN_CLINICAL_EVAL not set")

    raw_key = os.environ.get("VAULT_MASTER_KEY", "")
    if not raw_key:
        pytest.skip("VAULT_MASTER_KEY not set in .env")

    try:
        real_master_key = base64.b64decode(raw_key)
    except Exception as exc:
        pytest.skip(f"VAULT_MASTER_KEY is not valid base64: {exc}")

    # Patch _MASTER_KEY for the duration of the credential fetch only.
    import app.core.crypto as _crypto

    original_key = _crypto._MASTER_KEY
    _crypto._MASTER_KEY = real_master_key
    try:
        loop = asyncio.new_event_loop()
        try:
            cred = loop.run_until_complete(_fetch_gemini_cred())
        finally:
            loop.close()
    except Exception as exc:
        _crypto._MASTER_KEY = original_key
        pytest.skip(f"Could not load Gemini credential: {exc}")
    else:
        _crypto._MASTER_KEY = original_key

    return cred


# ---------------------------------------------------------------------------
# Compiled graph — built once per session with the real credential.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def clinical_graph(gemini_cred):
    """Compiled LangGraph backed by real Gemini."""
    from app.orchestrator.graph import build_graph

    return build_graph(gemini_cred)


# ---------------------------------------------------------------------------
# Result collector — accumulates per-case metrics; report is written at
# session end via pytest_sessionfinish.
# ---------------------------------------------------------------------------

_SESSION_RESULTS: list[dict] = []


@pytest.fixture(scope="session")
def eval_results() -> list[dict]:
    """Shared mutable list; each test appends its result dict here."""
    return _SESSION_RESULTS


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Write aggregate eval report after the session ends."""
    if not _SESSION_RESULTS:
        return

    import json
    import statistics
    from datetime import datetime, timezone

    results = _SESSION_RESULTS
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    reports_dir = Path(__file__).parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / f"eval_{ts}.json"

    n = len(results)

    def _rate(key: str) -> float:
        return sum(1 for r in results if r.get(key)) / n if n else 0.0

    latencies = [r["latency_seconds"] for r in results]
    latencies_sorted = sorted(latencies)

    def _percentile(data: list[float], p: int) -> float:
        if not data:
            return 0.0
        idx = max(0, int(len(data) * p / 100) - 1)
        return data[min(idx, len(data) - 1)]

    # Per-category breakdown
    categories: dict[str, dict] = {}
    for r in results:
        cat = r.get("category", "unknown")
        if cat not in categories:
            categories[cat] = {"total": 0, "triage_pass": 0, "escalation_pass": 0}
        categories[cat]["total"] += 1
        if r.get("triage_match"):
            categories[cat]["triage_pass"] += 1
        if r.get("escalation_match"):
            categories[cat]["escalation_pass"] += 1

    # Red flag recall macro avg (only cases with expected flags)
    rf_cases = [r for r in results if r.get("expected_flag_count", 0) > 0]
    rf_recall_avg = (
        sum(r["red_flag_recall"] for r in rf_cases) / len(rf_cases) if rf_cases else None
    )

    aggregate = {
        "timestamp": ts,
        "total_cases": n,
        "triage_accuracy": _rate("triage_match"),
        "escalation_accuracy": _rate("escalation_match"),
        "forbidden_diagnosis_avoidance_rate": _rate("forbidden_diagnosis_avoided"),
        "disclaimer_presence_rate": _rate("disclaimer_present"),
        "red_flag_recall_macro_avg": rf_recall_avg,
        "latency_p50_seconds": _percentile(latencies_sorted, 50),
        "latency_p95_seconds": _percentile(latencies_sorted, 95),
        "per_category": categories,
    }

    report = {"aggregate": aggregate, "cases": results}

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Print summary to terminal
    print(f"\n{'='*60}")
    print("CLINICAL EVAL REPORT")
    print(f"{'='*60}")
    print(f"Cases:              {n}")
    print(f"Triage accuracy:    {aggregate['triage_accuracy']:.1%}")
    print(f"Escalation acc.:    {aggregate['escalation_accuracy']:.1%}")
    print(f"Forbidden diag.:    {aggregate['forbidden_diagnosis_avoidance_rate']:.1%}")
    print(f"Disclaimer rate:    {aggregate['disclaimer_presence_rate']:.1%}")
    if rf_recall_avg is not None:
        print(f"Red flag recall:    {rf_recall_avg:.1%}")
    print(f"Latency P50/P95:    {aggregate['latency_p50_seconds']:.1f}s / {aggregate['latency_p95_seconds']:.1f}s")
    print(f"Report saved to:    {report_path}")
    print(f"{'='*60}\n")
