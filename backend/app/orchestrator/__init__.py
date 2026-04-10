# orchestrator/__init__.py
#
# Only re-export the TypedDict from state.py — which has NO further imports
# into the agents layer. graph.py (which imports agents) must NOT be imported
# here because agents themselves import from orchestrator.state, causing a
# circular import if __init__ eagerly loads graph.py.
#
# Consumers that need build_graph / create_initial_state / LOOP_CONFIG should
# import directly from app.orchestrator.graph.

from app.orchestrator.state import ClinicalCaseState

__all__ = ["ClinicalCaseState"]
