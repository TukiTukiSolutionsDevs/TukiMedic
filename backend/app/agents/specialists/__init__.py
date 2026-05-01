# Import all specialist modules to trigger @register decorators.
# Order matters: registry must be imported before agents.
from app.agents.specialists.schemas import DiagnosisHypothesis, SpecialistAnalysis
from app.agents.specialists.base import BaseSpecialistAgent
from app.agents.specialists.registry import REGISTRY, get_specialist, get_available_specialties

# Specialists — each module registers itself via @register on import
from app.agents.specialists.general_medicine import GeneralMedicineAgent
from app.agents.specialists.internal_medicine import InternalMedicineAgent
from app.agents.specialists.pediatrics import PediatricsAgent
from app.agents.specialists.gynecology import GynecologyAgent
from app.agents.specialists.cardiology import CardiologyAgent
from app.agents.specialists.traumatology import TraumatologyAgent
from app.agents.specialists.neurology import NeurologyAgent
from app.agents.specialists.pharmacology import PharmacologyAgent, PharmacologyAnalysis, DrugInteraction

from app.agents.specialists.dispatcher import dispatch_specialists

__all__ = [
    # Schemas
    "DiagnosisHypothesis",
    "SpecialistAnalysis",
    "PharmacologyAnalysis",
    "DrugInteraction",
    # Base
    "BaseSpecialistAgent",
    # Registry
    "REGISTRY",
    "get_specialist",
    "get_available_specialties",
    # Agents
    "GeneralMedicineAgent",
    "InternalMedicineAgent",
    "PediatricsAgent",
    "GynecologyAgent",
    "CardiologyAgent",
    "TraumatologyAgent",
    "NeurologyAgent",
    "PharmacologyAgent",
    # Dispatcher
    "dispatch_specialists",
]
