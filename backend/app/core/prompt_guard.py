"""Prompt injection defenses.

Two complementary mechanisms:

1. **Detection** (`detect_injection`) — deterministic regex pre-filter that
   matches known prompt-injection patterns BEFORE the user's message hits
   any LLM. Catches the cheap, common cases ("ignore all previous
   instructions", role overrides, delimiter breaks, unicode obfuscation).

2. **Containment** (`wrap_user_input`) — wraps untrusted input in explicit
   delimiters and normalizes Unicode (NFKC + strip of zero-width / RTL
   override chars). The wrapper instructs the LLM to treat the contents
   as DATA, not instructions.

Both are stdlib-only (no new dependency). Combined they cover ~80% of
the prompt-injection surface; the remaining 20% requires LLM-based
detection at the guardrail layer (separate prompt section).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


# Compiled patterns for known prompt-injection vectors. Match is
# case-insensitive and operates on Unicode-normalized text.
_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore_previous_instructions",
        re.compile(
            # accents handled via accent-stripped normalization (see
            # _normalize_for_detection); patterns use ASCII only.
            r"\b(ignor[ae]r?|olvid[ae]r?|disregard|forget)\b[^.]{0,40}\b"
            r"(all|previous|prior|prev|todas?|previas?|anteriores?)\b"
            r"[^.]{0,40}\b(instructions?|prompts?|instruccion(es)?|directiv(as|os)|reglas)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "role_override",
        re.compile(
            r"\b(you are now|act(ing)? as|pretend(ing)? to be|sos ahora|"
            r"actuá como|hacé de cuenta que sos|DAN mode|jailbreak)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "delimiter_break",
        re.compile(
            r"</?\s*(system|user|assistant|tool|function)\s*>",
            re.IGNORECASE,
        ),
    ),
    (
        "system_marker_override",
        re.compile(
            r"^\s*(system|sistema|developer|instrucción del sistema)\s*[:=]\s*",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        "leak_prompt",
        re.compile(
            r"\b(reveal|repeat|print|imprim[ai]r?|mostr[áa]r?)\b[^.]{0,40}\b"
            r"(system\s*prompt|initial\s*prompt|prompt\s*completo|"
            r"system\s*message|tus\s*instrucciones)\b",
            re.IGNORECASE,
        ),
    ),
)

# Zero-width and direction-override Unicode characters often used to
# obfuscate prompts visually.
_DANGEROUS_UNICODE = re.compile(
    r"[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]"
)


@dataclass(frozen=True)
class InjectionVerdict:
    matched: bool
    patterns: tuple[str, ...]

    @property
    def reason(self) -> str:
        return ", ".join(self.patterns) if self.patterns else ""


def _strip_accents(text: str) -> str:
    """Remove combining marks via NFKD decomposition.

    Done only for INJECTION DETECTION so the regex patterns can stay
    ASCII-only ("olvida" matches both "olvida" and "olvidá"). The
    ``wrap_user_input`` path uses NFKC + dangerous-char stripping but
    preserves accents for the LLM (so the patient's text stays correct).
    """
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _normalize_for_detection(text: str) -> str:
    """NFKC + accent-strip + remove zero-width / direction-override chars."""
    nfkc = unicodedata.normalize("NFKC", text or "")
    cleaned = _DANGEROUS_UNICODE.sub("", nfkc)
    return _strip_accents(cleaned)


def _normalize_for_wrap(text: str) -> str:
    """NFKC + remove zero-width / direction-override chars only.

    Preserves accents — what the LLM receives must remain the patient's
    real text minus invisible obfuscation characters.
    """
    nfkc = unicodedata.normalize("NFKC", text or "")
    return _DANGEROUS_UNICODE.sub("", nfkc)


def detect_injection(text: str) -> InjectionVerdict:
    """Run regex pre-filter against the message.

    Returns InjectionVerdict(matched, patterns) where `patterns` is the
    tuple of named patterns that fired. If no pattern matches, returns
    `InjectionVerdict(False, ())`.

    Defensive: empty / None input is treated as benign (matched=False).
    """
    if not text:
        return InjectionVerdict(False, ())
    normalized = _normalize_for_detection(text)
    matched: list[str] = []
    for name, pattern in _INJECTION_PATTERNS:
        if pattern.search(normalized):
            matched.append(name)
    return InjectionVerdict(matched=bool(matched), patterns=tuple(matched))


# Delimiters used to wrap untrusted input when injecting it into an LLM
# context. Chosen to be unlikely in real clinical messages and to be
# explicitly named by the surrounding system prompt as "data, not
# instructions".
_USER_INPUT_OPEN = "<<<USER_INPUT>>>"
_USER_INPUT_CLOSE = "<<<END_USER_INPUT>>>"


def wrap_user_input(text: str) -> str:
    """Wrap untrusted input in explicit delimiters and clean it.

    - Normalizes via NFKC (preserves accents — the LLM still gets the
      patient's real wording).
    - Strips zero-width / direction-override Unicode chars (visual spoof
      vectors only).
    - Removes any embedded delimiter that matches our open/close marker
      so the user cannot smuggle a fake closing tag.
    - Returns the cleaned text wrapped between the open and close marker.
    """
    cleaned = _normalize_for_wrap(text or "")
    cleaned = cleaned.replace(_USER_INPUT_OPEN, "").replace(_USER_INPUT_CLOSE, "")
    return f"{_USER_INPUT_OPEN}\n{cleaned}\n{_USER_INPUT_CLOSE}"
