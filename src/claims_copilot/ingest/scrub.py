"""Redact AMA CPT descriptor text from extracted source text (hard rule 3).

CMS and OIG documents mostly cite CPT codes as bare numbers, but some (notably NCCI Policy
Manual chapters) print a code followed by its descriptor, e.g. `12345 (Widget frobnication; ...)`.
We keep the code (a number) and replace the descriptor with a placeholder. Detection is
deliberately conservative: it over-redacts rather than under-redacts.

Known limits, recorded in DECISIONS.md: this catches `code (descriptor)` and `code - Descriptor`
shapes. It cannot detect verbatim CPT guideline prose quoted without a code, nor descriptors laid
out in tables that PDF extraction scrambles. Those residual risks are why raw and extracted files
are never committed.

Redaction logs carry the code, page, rule, length and a SHA-256 of the removed text, never the
text itself.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

PLACEHOLDER = "[CPT descriptor redacted]"
MAX_PAREN_CHARS = 600
MIN_PAREN_CHARS = 8

_CODE = r"(?:[0-9]{5}|[0-9]{4}[FTU])"
_CODE_RE = re.compile(rf"(?<![\w.$/-])({_CODE})(?![\w%/-])")
_DASH_RE = re.compile(rf"(?<![\w.$/-])({_CODE})[ \t]*[-\u2013\u2014:][ \t]*([A-Z][^\n.]{{6,160}})")
# A code at the start of a line followed by capitalised text: a table-style "code descriptor" row.
_LINE_RE = re.compile(rf"(?m)^[ \t]*({_CODE})[ \t]{{1,3}}([A-Z][^\n]{{8,160}})$")
# Mid-line "code Descriptor, with; punctuation" (e.g. "report 12345 Widget frobnication; single").
_INLINE_RE = re.compile(rf"(?<![\w.$/-])({_CODE})[ \t]{{1,3}}([A-Z][a-z]{{3,}}[^\n.]{{6,160}})")
_CONTINUATION_RE = re.compile(r"\n[ \t]*[a-z][^\n]{0,160}")
_CITATION_LOOKBEHIND = re.compile(r"(?:Fed\.?\s*Reg\.?|\bFR|\bU\.S\.C\.?|\bCFR)\s*$")
MAX_CONTINUATION_LINES = 2
# Parenthetical commentary written by CMS (not a descriptor) starts with one of these.
_COMMENTARY_STARTS = (
    "or ",
    "and ",
    "the ",
    "see ",
    "i.e.",
    "e.g.",
    "formerly",
    "effective",
    "deleted",
    "now ",
    "including",
    "codes ",
    "code ",
    "modifier",
    "rev.",
)


@dataclass(frozen=True)
class Redaction:
    code: str
    rule: str
    chars: int
    sha256: str


def _balanced_paren_end(text: str, open_idx: int) -> int | None:
    depth = 0
    limit = min(len(text), open_idx + MAX_PAREN_CHARS + 2)
    for i in range(open_idx, limit):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return None


def _extend_continuation(text: str, end: int) -> int:
    """Absorb wrapped lines (starting lowercase) that continue a descriptor."""
    for _ in range(MAX_CONTINUATION_LINES):
        m = _CONTINUATION_RE.match(text, end)
        if m is None:
            break
        end = m.end()
    return end


def _is_citation(text: str, code_start: int) -> bool:
    return bool(_CITATION_LOOKBEHIND.search(text[max(0, code_start - 20) : code_start]))


def _is_commentary(inner: str) -> bool:
    return inner.lstrip().lower().startswith(_COMMENTARY_STARTS)


def _digest(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", text).strip().encode("utf-8")).hexdigest()


def scrub(text: str) -> tuple[str, list[Redaction]]:
    """Return (scrubbed_text, redactions). Idempotent: scrubbing twice changes nothing more."""
    spans: list[tuple[int, int, str, Redaction]] = []
    for m in _CODE_RE.finditer(text):
        after = m.end()
        j = after
        while j < len(text) and text[j] in " \t\n\r":
            j += 1
        if _is_citation(text, m.start()):
            continue
        if j < len(text) and text[j] == "(" and j - after <= 3:
            end = _balanced_paren_end(text, j)
            if end is not None:
                inner = text[j + 1 : end]
                if (
                    MIN_PAREN_CHARS <= len(inner.strip()) <= MAX_PAREN_CHARS
                    and inner.strip() != PLACEHOLDER
                    and not _is_commentary(inner)
                ):
                    spans.append(
                        (
                            j + 1,
                            end,
                            f"{PLACEHOLDER}",
                            Redaction(m.group(1), "paren", len(inner), _digest(inner)),
                        )
                    )
    for rule, pattern in (("dash", _DASH_RE), ("line", _LINE_RE), ("inline", _INLINE_RE)):
        for m in pattern.finditer(text):
            desc = m.group(2)
            if rule == "inline" and "," not in desc and ";" not in desc:
                continue
            if PLACEHOLDER in desc or _is_commentary(desc) or _is_citation(text, m.start(1)):
                continue
            end = _extend_continuation(text, m.end(2))
            full = text[m.start(2) : end]
            spans.append(
                (
                    m.start(2),
                    end,
                    PLACEHOLDER,
                    Redaction(m.group(1), rule, len(full), _digest(full)),
                )
            )

    spans.sort(key=lambda s: s[0])
    out: list[str] = []
    redactions: list[Redaction] = []
    cursor = 0
    for start, end, replacement, redaction in spans:
        if start < cursor:  # overlapping match; the earlier span already covers it
            continue
        out.append(text[cursor:start])
        out.append(replacement)
        redactions.append(redaction)
        cursor = end
    out.append(text[cursor:])
    return "".join(out), redactions
