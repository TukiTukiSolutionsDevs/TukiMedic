"""Tests for OCR service — ALL mocked, no real Tesseract or Cloud Vision required."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ocr_data(confs: list[int]) -> dict:
    """Build a fake pytesseract.image_to_data result dict."""
    return {"conf": confs}


FAKE_JPEG = b"\xff\xd8\xff fake jpeg bytes"
FAKE_PNG = b"\x89PNG fake png bytes"
FAKE_PDF = b"%PDF-1.4 fake pdf bytes"


# ---------------------------------------------------------------------------
# T1 — success path: image returns text with high confidence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ocr_image_success():
    """pytesseract returns text with high confidence → engine=tesseract."""
    mock_img = MagicMock()

    with patch("app.services.ocr.pytesseract") as mock_pt, \
         patch("app.services.ocr.Image") as mock_pil:

        mock_pil.open.return_value = mock_img
        mock_pt.Output.DICT = "dict"
        mock_pt.image_to_data.return_value = _ocr_data([90, 85, 95])
        mock_pt.image_to_string.return_value = "Hemoglobina 14.5 g/dL"

        from app.services.ocr import ocr_document
        result = await ocr_document(FAKE_JPEG, "image/jpeg")

    assert result["text"] == "Hemoglobina 14.5 g/dL"
    assert result["confidence"] == pytest.approx(90.0)
    assert result["engine"] == "tesseract"


# ---------------------------------------------------------------------------
# T2 — return shape: dict has text, confidence and engine keys
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ocr_image_returns_text_and_confidence():
    """Result dict always contains text, confidence (avg) and engine keys."""
    mock_img = MagicMock()

    with patch("app.services.ocr.pytesseract") as mock_pt, \
         patch("app.services.ocr.Image") as mock_pil:

        mock_pil.open.return_value = mock_img
        mock_pt.Output.DICT = "dict"
        mock_pt.image_to_data.return_value = _ocr_data([70, 80])
        mock_pt.image_to_string.return_value = "Glucosa 95 mg/dL"

        from app.services.ocr import ocr_document
        result = await ocr_document(FAKE_PNG, "image/png")

    assert "text" in result
    assert "confidence" in result
    assert "engine" in result
    assert result["confidence"] == pytest.approx(75.0)


# ---------------------------------------------------------------------------
# T3 — PDF: convert_from_bytes is called; each page is OCR'd
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ocr_pdf_converts_pages():
    """pdf2image.convert_from_bytes called; one image_to_string call per page."""
    pages = [MagicMock(), MagicMock()]

    with patch("app.services.ocr.convert_from_bytes") as mock_cfb, \
         patch("app.services.ocr.pytesseract") as mock_pt:

        mock_cfb.return_value = pages
        mock_pt.Output.DICT = "dict"
        mock_pt.image_to_data.return_value = _ocr_data([80, 85])
        mock_pt.image_to_string.return_value = "page text"

        from app.services.ocr import ocr_document
        result = await ocr_document(FAKE_PDF, "application/pdf")

    mock_cfb.assert_called_once_with(FAKE_PDF)
    assert mock_pt.image_to_string.call_count == 2
    assert result["engine"] == "tesseract"


# ---------------------------------------------------------------------------
# T4 — PDF multi-page: texts joined with double newline
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ocr_pdf_multi_page():
    """3-page PDF → full_text = page texts joined by '\\n\\n'."""
    pages = [MagicMock() for _ in range(3)]

    with patch("app.services.ocr.convert_from_bytes") as mock_cfb, \
         patch("app.services.ocr.pytesseract") as mock_pt:

        mock_cfb.return_value = pages
        mock_pt.Output.DICT = "dict"
        mock_pt.image_to_data.return_value = _ocr_data([80])
        mock_pt.image_to_string.side_effect = ["Page 1 text", "Page 2 text", "Page 3 text"]

        from app.services.ocr import ocr_document
        result = await ocr_document(FAKE_PDF, "application/pdf")

    assert result["text"] == "Page 1 text\n\nPage 2 text\n\nPage 3 text"
    assert mock_pt.image_to_string.call_count == 3


# ---------------------------------------------------------------------------
# T5 — low confidence triggers Cloud Vision fallback when configured
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ocr_low_confidence_triggers_fallback():
    """avg_confidence < 60 AND short text → _try_cloud_vision called and used."""
    mock_img = MagicMock()
    cloud_result = {
        "text": "Cloud Vision extracted text",
        "confidence": 95.0,
        "engine": "cloud_vision",
    }

    with patch("app.services.ocr.pytesseract") as mock_pt, \
         patch("app.services.ocr.Image") as mock_pil, \
         patch("app.services.ocr._try_cloud_vision", new_callable=AsyncMock,
               return_value=cloud_result) as mock_cv:

        mock_pil.open.return_value = mock_img
        mock_pt.Output.DICT = "dict"
        mock_pt.image_to_data.return_value = _ocr_data([30, 25])  # avg=27.5 < 60
        mock_pt.image_to_string.return_value = "bad"              # len < 50

        from app.services.ocr import ocr_document
        result = await ocr_document(FAKE_JPEG, "image/jpeg")

    mock_cv.assert_called_once()
    assert result["engine"] == "cloud_vision"
    assert result["text"] == "Cloud Vision extracted text"
    assert result["confidence"] == 95.0


# ---------------------------------------------------------------------------
# T6 — no GCP creds → Tesseract result returned even with low confidence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ocr_cloud_vision_disabled():
    """GOOGLE_APPLICATION_CREDENTIALS absent → _try_cloud_vision returns None → tesseract wins."""
    mock_img = MagicMock()

    with patch("app.services.ocr.pytesseract") as mock_pt, \
         patch("app.services.ocr.Image") as mock_pil, \
         patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": ""}):
        # empty string is falsy → _try_cloud_vision returns None immediately
        mock_pil.open.return_value = mock_img
        mock_pt.Output.DICT = "dict"
        mock_pt.image_to_data.return_value = _ocr_data([25, 30])  # avg=27.5 < 60
        mock_pt.image_to_string.return_value = "bad"              # len < 50

        from app.services.ocr import ocr_document
        result = await ocr_document(FAKE_JPEG, "image/jpeg")

    assert result["engine"] == "tesseract"
    assert result["text"] == "bad"


# ---------------------------------------------------------------------------
# T7 — blank image: all -1 confidences → text="", confidence=0
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ocr_empty_image():
    """Image with no detectable text → empty string, confidence=0."""
    mock_img = MagicMock()

    with patch("app.services.ocr.pytesseract") as mock_pt, \
         patch("app.services.ocr.Image") as mock_pil:

        mock_pil.open.return_value = mock_img
        mock_pt.Output.DICT = "dict"
        mock_pt.image_to_data.return_value = _ocr_data([-1, -1, -1])  # no text
        mock_pt.image_to_string.return_value = ""

        from app.services.ocr import ocr_document
        result = await ocr_document(FAKE_JPEG, "image/jpeg")

    assert result["text"] == ""
    assert result["confidence"] == 0
    assert result["engine"] == "tesseract"


# ---------------------------------------------------------------------------
# T8 — unsupported MIME raises ValueError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ocr_unsupported_mime():
    """MIME types outside pdf/jpeg/png raise ValueError."""
    from app.services.ocr import ocr_document

    with pytest.raises(ValueError, match="Unsupported MIME type"):
        await ocr_document(b"data", "text/plain")

    with pytest.raises(ValueError, match="Unsupported MIME type"):
        await ocr_document(b"data", "image/gif")
