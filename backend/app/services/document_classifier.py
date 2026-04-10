"""Document classification via LLM structured output — Phase 2.3."""

from typing import Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

DOC_TYPES = Literal[
    "lab_result",
    "prescription",
    "medical_report",
    "imaging_report",
    "discharge_summary",
    "unknown",
]


class DocumentClassification(BaseModel):
    doc_type: str = Field(description="Type of medical document")
    confidence: float = Field(description="Confidence score 0-1")
    reasoning: str = Field(description="Brief explanation")


async def classify_document(ocr_text: str, api_key: str) -> DocumentClassification:
    """Classify a medical document based on its OCR text.

    Returns immediately with doc_type='unknown' if text is too short to classify.
    """
    if not ocr_text or len(ocr_text.strip()) < 10:
        return DocumentClassification(
            doc_type="unknown", confidence=0.0, reasoning="Insufficient text"
        )

    llm = ChatOpenAI(model="gpt-4o-mini", api_key=api_key, temperature=0)
    structured_llm = llm.with_structured_output(DocumentClassification)

    prompt = f"""Classify this medical document based on its content.

Document text:
{ocr_text[:2000]}

Classify as one of: lab_result, prescription, medical_report, imaging_report, discharge_summary, unknown"""

    result = await structured_llm.ainvoke(prompt)
    return result
