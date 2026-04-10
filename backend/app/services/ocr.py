"""OCR service — Tesseract with optional Cloud Vision fallback.

System dependencies required (NOT installable via pip):
  - tesseract-ocr  →  brew install tesseract
  - poppler-utils  →  brew install poppler
"""

import asyncio
import os
from functools import partial
from io import BytesIO

import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes

CONFIDENCE_THRESHOLD = 60  # below this, attempt Cloud Vision fallback


async def ocr_document(file_data: bytes, mime_type: str) -> dict:
    """OCR a document.

    Returns:
        {"text": str, "confidence": float, "engine": str}

    Raises:
        ValueError: if mime_type is not supported.
    """
    loop = asyncio.get_running_loop()

    if mime_type == "application/pdf":
        images = await loop.run_in_executor(
            None, partial(convert_from_bytes, file_data)
        )
    elif mime_type in ("image/jpeg", "image/png"):
        images = [Image.open(BytesIO(file_data))]
    else:
        raise ValueError(f"Unsupported MIME type for OCR: {mime_type}")

    texts: list[str] = []
    confidences: list[float] = []

    for img in images:
        # Confidence data — filter -1 (no text detected on that token)
        data = await loop.run_in_executor(
            None,
            partial(pytesseract.image_to_data, img, output_type=pytesseract.Output.DICT),
        )
        text = await loop.run_in_executor(
            None, partial(pytesseract.image_to_string, img)
        )
        texts.append(text.strip())

        valid_confs = [c for c in data["conf"] if c != -1]
        if valid_confs:
            confidences.append(sum(valid_confs) / len(valid_confs))

    full_text = "\n\n".join(texts)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    engine = "tesseract"

    # Fallback: low confidence AND very short output → try Cloud Vision
    if avg_confidence < CONFIDENCE_THRESHOLD and len(full_text.strip()) < 50:
        cloud_result = await _try_cloud_vision(file_data, mime_type)
        if cloud_result:
            return cloud_result

    return {"text": full_text, "confidence": avg_confidence, "engine": engine}


async def _try_cloud_vision(file_data: bytes, mime_type: str) -> dict | None:
    """Attempt Google Cloud Vision OCR.

    Returns None if GCP is not configured or the call fails.
    """
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return None

    try:
        from google.cloud import vision  # type: ignore[import-untyped]

        loop = asyncio.get_running_loop()
        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=file_data)
        response = await loop.run_in_executor(
            None, partial(client.text_detection, image=image)
        )
        if response.text_annotations:
            return {
                "text": response.text_annotations[0].description,
                "confidence": 95.0,  # Cloud Vision doesn't expose per-char confidence easily
                "engine": "cloud_vision",
            }
    except Exception:  # noqa: BLE001
        pass

    return None
