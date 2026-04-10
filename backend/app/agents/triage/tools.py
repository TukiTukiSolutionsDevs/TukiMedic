import yaml
from pathlib import Path
from dataclasses import dataclass


@dataclass
class RedFlagMatch:
    matched: bool
    category: str | None = None
    trigger: str | None = None
    details: str = ""


# Load red flags at module level (cached)
_RED_FLAGS_PATH = Path(__file__).parent.parent.parent.parent / "data" / "red_flags.yaml"
_RED_FLAGS: dict[str, list[str]] = {}


def _load_red_flags() -> dict[str, list[str]]:
    global _RED_FLAGS
    if not _RED_FLAGS:
        with open(_RED_FLAGS_PATH, "r", encoding="utf-8") as f:
            _RED_FLAGS = yaml.safe_load(f)
    return _RED_FLAGS


def red_flag_checker(message: str) -> list[RedFlagMatch]:
    """Check message against known red flags. Pre-LLM filter — no tokens spent."""
    red_flags = _load_red_flags()
    message_lower = message.lower()
    matches = []

    for category, triggers in red_flags.items():
        for trigger in triggers:
            if trigger.lower() in message_lower:
                matches.append(RedFlagMatch(
                    matched=True,
                    category=category,
                    trigger=trigger,
                    details=f"Red flag '{trigger}' detectado en categoría '{category}'"
                ))

    return matches


def symptom_scorer(symptoms: list[str]) -> float:
    """Score symptom severity. Returns 0.0 (mild) to 1.0 (severe).
    Simple heuristic — will be enhanced with LLM in production."""
    if not symptoms:
        return 0.0

    severity_keywords = {
        "severo": 0.9, "grave": 0.9, "intenso": 0.8, "agudo": 0.8,
        "fuerte": 0.7, "moderado": 0.5, "leve": 0.2, "ligero": 0.1,
        "insoportable": 1.0, "terrible": 0.9, "horrible": 0.8,
    }

    max_score = 0.3  # base score for having any symptom
    for symptom in symptoms:
        symptom_lower = symptom.lower()
        for keyword, score in severity_keywords.items():
            if keyword in symptom_lower:
                max_score = max(max_score, score)

    return min(max_score, 1.0)


def age_risk_evaluator(age: int | None, symptoms: list[str]) -> float:
    """Evaluate age-related risk multiplier."""
    if age is None:
        return 1.0

    # Higher risk for very young and elderly
    if age < 1:
        return 1.5  # Neonates
    elif age < 5:
        return 1.3  # Young children
    elif age > 85:
        return 1.5  # Very elderly
    elif age > 70:
        return 1.3  # Elderly

    return 1.0
