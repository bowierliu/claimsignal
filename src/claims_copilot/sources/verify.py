"""Deterministic checks that a fetched document is what the catalog says it is.

This verifies identity (expected title/number phrases appear in the opening text) and that a
quoted terms statement appears verbatim in a fetched terms page. It does not judge whether any
claim made elsewhere is supported by the text; that is a separate, later check.
"""

from __future__ import annotations

import io
import re
import unicodedata
import zipfile

from pypdf import PdfReader

from claims_copilot.sources.catalog import Kind

PDF_OPENING_PAGES = 3
MARKUP_OPENING_CHARS = 6000
ZIP_MEMBER_OPENING_CHARS = 2000

_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2212"), ord("-"))
_QUOTES = {
    ord("\u2018"): ord("'"),
    ord("\u2019"): ord("'"),
    ord("\u201c"): ord('"'),
    ord("\u201d"): ord('"'),
}
_TAGS = re.compile(r"<[^>]+>")
_SCRIPT_STYLE = re.compile(r"<(script|style)\b.*?</\1>", re.IGNORECASE | re.DOTALL)


class ExtractionError(RuntimeError):
    pass


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_DASHES).translate(_QUOTES)
    return re.sub(r"\s+", " ", text).strip().lower()


def markup_to_text(content: bytes) -> str:
    raw = content.decode("utf-8", errors="replace")
    raw = _SCRIPT_STYLE.sub(" ", raw)
    return re.sub(r"\s+", " ", _TAGS.sub(" ", raw))


def pdf_pages(content: bytes, *, max_pages: int | None = None) -> list[str]:
    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise ExtractionError("PDF is encrypted")
        pages = reader.pages if max_pages is None else reader.pages[:max_pages]
        return [page.extract_text() or "" for page in pages]
    except ExtractionError:
        raise
    except Exception as exc:  # pypdf raises many types on malformed input
        raise ExtractionError(f"{type(exc).__name__}: {exc}") from exc


def zip_opening_text(content: bytes) -> str:
    """Member names plus the first characters of each `.txt` member (identity check only)."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            bad = archive.testzip()
            if bad is not None:
                raise ExtractionError(f"corrupt zip member {bad}")
            parts = [info.filename for info in archive.infolist()]
            for info in archive.infolist():
                if info.filename.lower().endswith(".txt"):
                    with archive.open(info) as member:
                        head = member.read(ZIP_MEMBER_OPENING_CHARS * 4)
                    parts.append(head.decode("utf-8", errors="replace")[:ZIP_MEMBER_OPENING_CHARS])
    except ExtractionError:
        raise
    except Exception as exc:  # zipfile raises several types on malformed input
        raise ExtractionError(f"{type(exc).__name__}: {exc}") from exc
    return "\n".join(parts)


def opening_text(content: bytes, kind: Kind) -> str:
    if kind == "zip":
        return zip_opening_text(content)
    if kind == "pdf":
        return "\n".join(pdf_pages(content, max_pages=PDF_OPENING_PAGES))
    return markup_to_text(content)[:MARKUP_OPENING_CHARS]


def full_text(content: bytes, kind: Kind) -> str:
    if kind == "zip":
        raise ExtractionError("zip archives are identity-checked only; no full-text extraction")
    if kind == "pdf":
        return "\n".join(pdf_pages(content))
    return markup_to_text(content)


def missing_phrases(text: str, phrases: tuple[str, ...]) -> list[str]:
    haystack = normalize(text)
    return [p for p in phrases if normalize(p) not in haystack]


def contains_quote(text: str, quote: str) -> bool:
    return bool(quote.strip()) and normalize(quote) in normalize(text)
