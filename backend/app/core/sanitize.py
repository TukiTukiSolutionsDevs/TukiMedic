"""Patient-facing output sanitizer.

Defensive cleanup of any text that will be rendered to a patient. The
synthesizer LLM produces Markdown — we MUST strip the small set of
vectors that turn benign Markdown into XSS / phishing / pixel-tracking:

  - HTML tags entirely (script, iframe, img, style, svg, object, etc.)
  - Inline event handlers (onerror=, onclick=, ...) — covered when we
    strip whole tags, but we also normalize defensively.
  - Markdown links to dangerous URL schemes (javascript:, data:,
    vbscript:, file:) — rewritten to an inert anchor.
  - Markdown image references (we don't allow embedded images at all
    from LLM output — too easy to leak IP via a tracking pixel).
  - Zero-width / direction-override Unicode characters (homograph and
    visual-spoof vectors).

Intentionally stdlib-only (no `bleach` dependency) — keeps Docker images
small and lets us validate inside the container without rebuilds.

This sanitizer is conservative: when uncertain, strip rather than
preserve. The synthesizer prompt expects plain Markdown for clinical
guidance, so we lose nothing by being strict.
"""

from __future__ import annotations

import re
import unicodedata


# Characters that are valid as plain whitespace; everything else in the C
# (control) Unicode category gets stripped.
_KEEP_CONTROL_CHARS = {"\n", "\t", " "}

# Block tags entirely. We do NOT try to allowlist-render Markdown HTML
# fragments — the synthesizer is supposed to emit pure Markdown, so any
# raw HTML in the output is suspect.
_HTML_TAG_RE = re.compile(r"<[^>]+>", re.DOTALL)

# Markdown image syntax: ![alt](url). We strip these entirely (LLM
# shouldn't be embedding remote images for a patient response).
_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")

# Markdown links with dangerous schemes. Group capture preserves the link
# text; we replace the URL with `#` (inert) so the patient still sees the
# label without an exploitable href.
_DANGEROUS_LINK_RE = re.compile(
    r"\[([^\]]*)\]\(\s*(?:javascript|data|vbscript|file)\s*:[^)]*\)",
    re.IGNORECASE,
)

# Bare URLs with dangerous schemes outside Markdown link syntax. We just
# remove the scheme so the rest reads as plain text.
_DANGEROUS_BARE_URL_RE = re.compile(
    r"\b(?:javascript|vbscript|data|file)\s*:[^\s)]+",
    re.IGNORECASE,
)


def _strip_dangerous_unicode(text: str) -> str:
    out_chars: list[str] = []
    for ch in text:
        if ch in _KEEP_CONTROL_CHARS:
            out_chars.append(ch)
            continue
        cat = unicodedata.category(ch)
        # Cf = format chars (zero-width, direction-override, BOM, etc.)
        # Cc = control chars (NUL, etc.)
        if cat in ("Cf", "Cc"):
            continue
        out_chars.append(ch)
    return "".join(out_chars)


def sanitize_patient_markdown(text: str | None) -> str:
    """Return a sanitized version of LLM-generated patient text.

    Idempotent. Empty / None input returns "".
    """
    if not text:
        return ""
    cleaned = unicodedata.normalize("NFKC", text)
    cleaned = _strip_dangerous_unicode(cleaned)
    cleaned = _HTML_TAG_RE.sub("", cleaned)
    cleaned = _MD_IMAGE_RE.sub("", cleaned)
    cleaned = _DANGEROUS_LINK_RE.sub(r"[\1](#)", cleaned)
    cleaned = _DANGEROUS_BARE_URL_RE.sub("", cleaned)
    return cleaned
