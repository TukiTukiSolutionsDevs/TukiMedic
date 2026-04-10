"""Medical Board agent package."""

from app.agents.medical_board.schemas import MedicalBoardResult, ChallengeResponse
from app.agents.medical_board.agent import MedicalBoardAgent, medical_board_router

__all__ = [
    "MedicalBoardAgent",
    "MedicalBoardResult",
    "ChallengeResponse",
    "medical_board_router",
]
