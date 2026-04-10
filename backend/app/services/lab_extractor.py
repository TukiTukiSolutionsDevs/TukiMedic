"""Lab value extraction via LLM structured output — Phase 2.4."""

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


class ExtractedLabValue(BaseModel):
    test_name: str = Field(description="Name of the lab test")
    value: str = Field(description="Result value")
    unit: str | None = Field(default=None, description="Unit of measurement")
    reference_range: str | None = Field(default=None, description="Normal reference range")
    flag: str | None = Field(default=None, description="high, low, normal, or critical")


class LabExtractionResult(BaseModel):
    values: list[ExtractedLabValue] = Field(default_factory=list)


async def extract_lab_values(ocr_text: str, api_key: str) -> list[ExtractedLabValue]:
    """Extract all lab test results from OCR text of a lab result document.

    Returns an empty list if text is too short to process.
    """
    if not ocr_text or len(ocr_text.strip()) < 10:
        return []

    llm = ChatOpenAI(model="gpt-4o-mini", api_key=api_key, temperature=0)
    structured_llm = llm.with_structured_output(LabExtractionResult)

    prompt = f"""Extract all laboratory test results from this document.
For each test, identify: test name, value, unit, reference range, and flag (high/low/normal/critical).

Document text:
{ocr_text[:3000]}"""

    result = await structured_llm.ainvoke(prompt)
    return result.values
