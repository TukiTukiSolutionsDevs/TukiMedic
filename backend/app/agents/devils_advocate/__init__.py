"""Devil's Advocate agent package."""

from app.agents.devils_advocate.schemas import ChallengeResult, Challenge
from app.agents.devils_advocate.agent import DevilsAdvocateAgent

__all__ = [
    "DevilsAdvocateAgent",
    "ChallengeResult",
    "Challenge",
]
