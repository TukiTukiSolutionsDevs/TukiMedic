"""
Sprint 2 — security hardening regression tests.

Covers fixes T2.12 (OCR timeout / page cap) and T2.13 (filename sanitisation
against path traversal, control bytes, shell metacharacters).
"""
from __future__ import annotations

import asyncio
from io import BytesIO
from unittest.mock import patch

import pytest
from PIL import Image

from app.api.v1.documents import sanitize_filename


# ===========================================================================
# T2.13 — sanitize_filename
# ===========================================================================


class TestSanitizeFilename:
    def test_strips_traversal(self):
        # os.path.basename discards everything before the last separator —
        # the entire ../.. prefix is gone, leaving only the leaf name.
        assert sanitize_filename("../../etc/passwd") == "passwd"

    def test_strips_absolute_path(self):
        assert sanitize_filename("/var/log/syslog") == "syslog"

    def test_collapses_special_chars(self):
        # Spaces, semicolons, dashes (other than literal '-') are replaced.
        assert sanitize_filename("foo bar;rm.pdf") == "foo_bar_rm.pdf"

    def test_strips_null_byte(self):
        assert "\x00" not in sanitize_filename("foo\x00.pdf")

    def test_drops_leading_dot(self):
        assert sanitize_filename(".hidden") == "hidden"

    def test_caps_length(self):
        long_name = "a" * 500 + ".pdf"
        result = sanitize_filename(long_name)
        assert len(result) <= 200
        assert result.endswith(".pdf")

    def test_preserves_unicode_letters_via_underscore(self):
        # "résumé.pdf" — non-ASCII letters collapse to _
        result = sanitize_filename("résumé.pdf")
        # Cannot assume specific replacement, just that it's safe
        assert "/" not in result
        assert ".." not in result
        assert result.endswith(".pdf")

    def test_empty_returns_fallback(self):
        assert sanitize_filename("") == "upload"
        assert sanitize_filename(None) == "upload"

    def test_only_special_chars_returns_fallback(self):
        assert sanitize_filename("///...///") == "upload"

    def test_keeps_valid_alphanumeric(self):
        assert sanitize_filename("Lab-2024_results.pdf") == "Lab-2024_results.pdf"


# ===========================================================================
# S4.0.a-3 — RBAC: UserResponse must expose role and subscription_tier
# ===========================================================================

from unittest.mock import MagicMock as _MagicMock  # noqa: E402


class TestRoleAuthPayloads:
    """UserResponse schema must include role/subscription_tier (S4.0.a-3)."""

    def test_user_response_has_role_field(self):
        from app.schemas.auth import UserResponse

        assert "role" in UserResponse.model_fields, \
            "UserResponse must expose 'role' field"

    def test_user_response_has_subscription_tier_field(self):
        from app.schemas.auth import UserResponse

        assert "subscription_tier" in UserResponse.model_fields, \
            "UserResponse must expose 'subscription_tier' field"

    def test_user_response_serializes_customer_role(self):
        import uuid
        from app.schemas.auth import UserResponse

        obj = _MagicMock()
        obj.id = uuid.uuid4()
        obj.email = "u@x.com"
        obj.display_name = None
        obj.is_verified = False
        obj.role = "customer"
        obj.subscription_tier = "free"

        r = UserResponse.model_validate(obj)
        assert r.role == "customer"
        assert r.subscription_tier == "free"

    def test_user_response_serializes_admin_role(self):
        import uuid
        from app.schemas.auth import UserResponse

        obj = _MagicMock()
        obj.id = uuid.uuid4()
        obj.email = "admin@x.com"
        obj.display_name = "Admin"
        obj.is_verified = True
        obj.role = "admin"
        obj.subscription_tier = "free"

        r = UserResponse.model_validate(obj)
        assert r.role == "admin"


# ===========================================================================
# T2.12 — OCR timeout / page cap
# ===========================================================================


def _png_bytes() -> bytes:
    """Return a minimal valid PNG (1x1 px) so PIL can open it."""
    img = Image.new("RGB", (1, 1), color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestOcrTimeout:
    @pytest.mark.asyncio
    async def test_per_page_timeout_propagates(self):
        """If tesseract hangs longer than budget, ocr_document raises TimeoutError."""
        from app.services import ocr

        # Simulate a slow tesseract call by making run_in_executor await forever.
        async def _hang(*args, **kwargs):
            await asyncio.sleep(60)  # well past per-page budget

        with patch.object(ocr, "PER_PAGE_OCR_TIMEOUT_S", 0.05), \
             patch("asyncio.get_running_loop") as mock_loop:
            loop = mock_loop.return_value
            loop.run_in_executor.side_effect = _hang

            with pytest.raises(asyncio.TimeoutError):
                await ocr.ocr_document(_png_bytes(), "image/jpeg")

    @pytest.mark.asyncio
    async def test_pdf_render_timeout_propagates(self):
        """If pdf2image rasterisation exceeds budget, ocr_document raises."""
        from app.services import ocr

        async def _hang(*args, **kwargs):
            await asyncio.sleep(60)

        with patch.object(ocr, "PDF_RENDER_TIMEOUT_S", 0.05), \
             patch("asyncio.get_running_loop") as mock_loop:
            loop = mock_loop.return_value
            loop.run_in_executor.side_effect = _hang

            with pytest.raises(asyncio.TimeoutError):
                await ocr.ocr_document(b"%PDF-1.4 fake", "application/pdf")

    @pytest.mark.asyncio
    async def test_pdf_page_cap_truncates(self):
        """PDFs with more than MAX_PDF_PAGES are truncated and flagged."""
        from app.services import ocr

        # Build a fake page list larger than the cap.
        fake_img = Image.new("RGB", (1, 1), color="white")
        too_many = [fake_img] * (ocr.MAX_PDF_PAGES + 5)

        async def _convert_executor(*args, **kwargs):
            return too_many

        async def _ocr_executor(*args, **kwargs):
            # Mimic tesseract output structure / strings
            func = args[1] if len(args) > 1 else kwargs.get("func")
            try:
                # data fn returns DICT with "conf"; string fn returns str
                result = func()
            except Exception:
                return ""
            return result

        # We patch run_in_executor to dispatch by callable kind.
        async def _exec(*args, **kwargs):
            # args are (executor, func) for run_in_executor
            func = args[1] if len(args) > 1 else None
            if func is None:
                return None
            # convert_from_bytes path
            if "convert_from_bytes" in repr(func):
                return too_many
            try:
                out = func()
            except Exception:
                return ""
            return out

        with patch("asyncio.get_running_loop") as mock_loop:
            loop = mock_loop.return_value
            loop.run_in_executor = _exec  # type: ignore[assignment]

            result = await ocr.ocr_document(b"%PDF-1.4 fake", "application/pdf")

            assert result.get("pages_truncated") is True
