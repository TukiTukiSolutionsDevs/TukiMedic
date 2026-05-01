"""Unit tests for sanitize_patient_markdown.

Covers the documented attack surface for LLM-generated patient text:
HTML tag injection, event handlers, dangerous URL schemes, embedded
images, and Unicode obfuscation. Also asserts clinical Markdown
(headings, lists, bold, italic, safe links) survives unchanged.
"""

import pytest

from app.core.sanitize import sanitize_patient_markdown


class TestStripsHtmlTags:
    def test_strips_script_tag(self):
        out = sanitize_patient_markdown("Hola <script>alert(1)</script> ¿qué tal?")
        assert "<script" not in out
        assert "alert" in out  # text content remains, just no tag
        # The text "alert(1)" between the tags should remain as plain text
        assert "Hola" in out and "¿qué tal?" in out

    def test_strips_iframe(self):
        out = sanitize_patient_markdown("texto <iframe src='evil'></iframe>")
        assert "<iframe" not in out
        assert "</iframe>" not in out

    def test_strips_img_tag_entirely(self):
        out = sanitize_patient_markdown('<img src="x" onerror="alert(1)">')
        assert "<img" not in out
        assert "onerror" not in out

    def test_strips_style_tag(self):
        out = sanitize_patient_markdown("<style>body{display:none}</style>texto")
        assert "<style" not in out
        assert "texto" in out

    def test_strips_svg_with_event_handler(self):
        out = sanitize_patient_markdown('<svg onload="alert(1)"><circle/></svg>texto')
        assert "<svg" not in out
        assert "onload" not in out
        assert "texto" in out


class TestStripsMarkdownImages:
    def test_strips_remote_image_reference(self):
        out = sanitize_patient_markdown("texto ![pixel](http://tracker.evil/x.gif) más texto")
        assert "tracker.evil" not in out
        assert "![pixel]" not in out
        assert "texto" in out and "más texto" in out

    def test_strips_data_url_image(self):
        out = sanitize_patient_markdown("![](data:image/svg+xml;base64,abc)")
        assert "data:" not in out
        assert "![" not in out


class TestRewritesDangerousLinks:
    def test_javascript_link_inert(self):
        out = sanitize_patient_markdown("[click](javascript:alert(1))")
        assert "javascript:" not in out
        assert "[click](#)" in out

    def test_vbscript_link_inert(self):
        out = sanitize_patient_markdown("[x](vbscript:msgbox())")
        assert "vbscript:" not in out
        assert "[x](#)" in out

    def test_data_url_link_inert(self):
        out = sanitize_patient_markdown("[x](data:text/html,<script>alert(1)</script>)")
        assert "data:" not in out
        assert "<script" not in out

    def test_safe_https_link_preserved(self):
        out = sanitize_patient_markdown("Más info en [Wikipedia](https://es.wikipedia.org/wiki/Migrana)")
        assert "https://es.wikipedia.org/wiki/Migrana" in out
        assert "[Wikipedia](https://es.wikipedia.org/wiki/Migrana)" in out


class TestStripsBareDangerousUrls:
    def test_strips_bare_javascript_url(self):
        out = sanitize_patient_markdown("Mira esto: javascript:alert(1)")
        assert "javascript:" not in out

    def test_strips_bare_data_url(self):
        out = sanitize_patient_markdown("data:text/html,<b>x</b>")
        assert "data:" not in out


class TestUnicodeHardening:
    def test_strips_zero_width_chars(self):
        evil = "Te recomiendo eval​uación médica"  # zero-width between l and u
        out = sanitize_patient_markdown(evil)
        assert "​" not in out
        assert "evaluación médica" in out

    def test_strips_rtl_override(self):
        evil = "click ‮aquí"
        out = sanitize_patient_markdown(evil)
        assert "‮" not in out

    def test_normalizes_full_width_chars(self):
        out = sanitize_patient_markdown("ＨＯＬＡ")
        assert "HOLA" in out


class TestPreservesClinicalMarkdown:
    @pytest.mark.parametrize("text", [
        "## Recomendación clínica",
        "**importante**: consultá con tu médico",
        "*Nota*: los síntomas pueden variar",
        "- Hidratate adecuadamente\n- Reposo\n- Control en 48hs",
        "1. Tomá la medicación que ya te indicaron\n2. Volvé si empeora",
        "Más información: [SAP](https://www.sap.org.ar/)",
        "Consultá si aparece dolor torácico, disnea o pérdida de conciencia.",
    ])
    def test_preserved(self, text):
        assert sanitize_patient_markdown(text) == text


class TestEdgeCases:
    def test_empty_string_returns_empty(self):
        assert sanitize_patient_markdown("") == ""

    def test_none_returns_empty(self):
        assert sanitize_patient_markdown(None) == ""

    def test_idempotent(self):
        once = sanitize_patient_markdown("<script>x</script>texto")
        twice = sanitize_patient_markdown(once)
        assert once == twice

    def test_does_not_mangle_em_dash_or_accents(self):
        text = "Es un síntoma común — no es grave en sí mismo."
        assert sanitize_patient_markdown(text) == text
