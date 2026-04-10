"""
Specialist Dispatcher — dynamic routing to registered specialist agents.

Reads active_specialties from state, instantiates matching agents from the
registry, runs them in parallel, and merges all specialist_outputs into one dict.

Fallback: if active_specialties is empty or no specialists match, runs
GeneralMedicineAgent as the default baseline.
"""

import asyncio

from app.agents.specialists.registry import get_specialist
from app.agents.specialists.general_medicine import GeneralMedicineAgent


async def dispatch_specialists(state: dict, api_key: str) -> dict:
    """
    Dispatch to active specialists in parallel. Fallback to general medicine.

    Args:
        state: ClinicalCaseState dict — reads active_specialties, specialist_outputs.
        api_key: User's API key injected into each specialist agent.

    Returns:
        Partial state update with merged specialist_outputs dict.
    """
    active = state.get("active_specialties", [])

    # --- Fallback: no active specialties ---
    if not active:
        agent = GeneralMedicineAgent(api_key=api_key)
        return await agent(state)

    # --- Resolve agents from registry ---
    agents = []
    for spec in active:
        # active_specialties items are dicts: {name, weight, reason}
        name = spec if isinstance(spec, str) else spec.get("name", "")
        agent = get_specialist(name, api_key)
        if agent is not None:
            agents.append(agent)

    # --- Fallback: no matching agents in registry ---
    if not agents:
        agent = GeneralMedicineAgent(api_key=api_key)
        return await agent(state)

    # --- Run all matched specialists in parallel ---
    results = await asyncio.gather(*[agent(state) for agent in agents])

    # --- Merge specialist_outputs (dict[str, dict]) ---
    merged_outputs: dict = {}
    for result in results:
        merged_outputs.update(result.get("specialist_outputs", {}))

    return {
        "specialist_outputs": merged_outputs,
        "current_node": "specialists_dispatched",
    }
