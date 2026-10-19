from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from claims_copilot.project import CATALOG_PATH
from claims_copilot.sources.catalog import CatalogError, load_catalog, parse_catalog
from claims_copilot.sources.fetch import build_row, failure_row
from claims_copilot.sources.http import FetchResult
from claims_copilot.sources.manifest import merge_rows, read_manifest, write_manifest
from claims_copilot.sources.verify import (
    ExtractionError,
    contains_quote,
    markup_to_text,
    missing_phrases,
    normalize,
    opening_text,
)


def tiny_pdf(text: str) -> bytes:
    """Build a one-page PDF containing `text` (ASCII, no parentheses)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return out


def entry_dict(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "source_id": "x1",
        "title": "Chapter 9 - Widgets",
        "publisher": "CMS",
        "url": "https://example.invalid/x1.pdf",
        "kind": "pdf",
        "expected_phrases": ["Chapter 9", "Widgets"],
    }
    base.update(overrides)
    return base


def test_normalize_unifies_dashes_quotes_case_and_space() -> None:
    assert normalize("Chapter\u00a01 \u2013  It\u2019s") == "chapter 1 - it's"


def test_pdf_opening_text_is_extracted_and_checked() -> None:
    text = opening_text(tiny_pdf("Chapter 9 Widgets and Gadgets"), "pdf")
    assert missing_phrases(text, ("chapter 9", "WIDGETS")) == []
    assert missing_phrases(text, ("Chapter 9", "Sprockets")) == ["Sprockets"]


def test_garbage_pdf_raises_extraction_error() -> None:
    with pytest.raises(ExtractionError):
        opening_text(b"not a pdf", "pdf")


def test_markup_to_text_drops_scripts_and_tags() -> None:
    html = b"<html><script>var a='secret';</script><body><p>Public <b>domain</b></p></body></html>"
    assert "secret" not in markup_to_text(html)
    assert contains_quote(markup_to_text(html), "public domain")
    assert not contains_quote("anything", "")


def test_catalog_validation() -> None:
    entries = parse_catalog({"source": [entry_dict()]})
    assert entries[0].source_id == "x1"
    with pytest.raises(CatalogError, match="duplicate"):
        parse_catalog({"source": [entry_dict(), entry_dict()]})
    with pytest.raises(CatalogError, match="https"):
        parse_catalog({"source": [entry_dict(url="http://example.invalid/a")]})
    with pytest.raises(CatalogError, match="expected_phrases"):
        parse_catalog({"source": [entry_dict(expected_phrases=[])]})
    with pytest.raises(CatalogError, match="unknown terms_source_id"):
        parse_catalog({"source": [entry_dict(terms_source_id="nope")]})


def test_real_catalog_is_consistent() -> None:
    entries = load_catalog(CATALOG_PATH)
    corpus = [e for e in entries if e.role == "corpus"]
    assert len(corpus) == 23
    terms_ids = {e.source_id for e in entries if e.role == "terms"}
    for e in corpus:
        assert e.terms_source_id in terms_ids or e.group == "ecfr", e.source_id
    assert not any("cpt" in e.source_id for e in entries)


def fake_result(content: bytes) -> FetchResult:
    return FetchResult(
        url="https://example.invalid/x1.pdf",
        final_url="https://example.invalid/x1.pdf",
        status=200,
        content_type="application/pdf",
        content=content,
        retrieved_at="2026-10-15T00:00:00+00:00",
        from_cache=False,
    )


def test_build_row_verified_and_mismatch() -> None:
    entry = parse_catalog({"source": [entry_dict()]})[0]
    ok = build_row(entry, fake_result(tiny_pdf("Chapter 9 Widgets")), Path("data/raw/x1.pdf"), {})
    assert ok["status"] == "VERIFIED"
    assert len(ok["sha256"]) == 64
    assert "UNVERIFIED" in ok["license_note"]
    bad = build_row(entry, fake_result(tiny_pdf("Chapter 9 Gadgets")), Path("data/raw/x1.pdf"), {})
    assert bad["status"] == "MISMATCH"
    assert bad["missing_phrases"] == ["Widgets"]


def test_build_row_unreadable_pdf_is_unverified() -> None:
    entry = parse_catalog({"source": [entry_dict()]})[0]
    row = build_row(entry, fake_result(b"garbage"), Path("data/raw/x1.pdf"), {})
    assert row["status"] == "UNVERIFIED"
    assert "extraction failed" in row["unverified_reason"]


def test_terms_quote_must_appear_verbatim_to_be_observed() -> None:
    quote = "It is a public domain web site."
    terms_entry = parse_catalog(
        {
            "source": [
                entry_dict(
                    source_id="t1",
                    role="terms",
                    kind="html",
                    expected_phrases=["public domain"],
                    terms_status="OBSERVED",
                    terms_quote=quote,
                )
            ]
        }
    )[0]
    page = f"<html><body>{quote}</body></html>".encode()
    row = build_row(terms_entry, fake_result(page), Path("data/raw/t1.html"), {})
    assert row["terms_status"] == "OBSERVED"
    wrong = build_row(
        terms_entry, fake_result(b"<html>It is a private site public domain</html>"), Path("t"), {}
    )
    assert wrong["terms_status"] == "UNVERIFIED"

    corpus = parse_catalog({"source": [entry_dict(terms_source_id="t1"), terms_entry_dict(quote)]})[
        0
    ]
    cited = build_row(corpus, fake_result(tiny_pdf("Chapter 9 Widgets")), Path("x"), {"t1": row})
    assert quote in cited["license_note"]
    assert "CPT" in cited["license_note"]
    assert cited["terms_status"] == "OBSERVED"


def terms_entry_dict(quote: str) -> dict[str, object]:
    return entry_dict(
        source_id="t1",
        role="terms",
        kind="html",
        expected_phrases=["public domain"],
        terms_status="OBSERVED",
        terms_quote=quote,
    )


def test_failure_row_is_unverified_without_hash() -> None:
    entry = parse_catalog({"source": [entry_dict()]})[0]
    row = failure_row(entry, "HTTP 404")
    assert row["status"] == "UNVERIFIED"
    assert row["sha256"] is None
    assert row["unverified_reason"] == "HTTP 404"


def test_manifest_roundtrip_sorts_and_merge_preserves_other_rows(tmp_path: Path) -> None:
    path = tmp_path / "m.jsonl"
    write_manifest(path, [{"source_id": "b", "v": 1}, {"source_id": "a", "v": 1}])
    rows = read_manifest(path)
    assert [r["source_id"] for r in rows] == ["a", "b"]
    merged = merge_rows(rows, [{"source_id": "b", "v": 2}, {"source_id": "c", "v": 1}])
    assert {r["source_id"]: r["v"] for r in merged} == {"a": 1, "b": 2, "c": 1}
    with pytest.raises(ValueError, match="duplicate"):
        write_manifest(path, [{"source_id": "a"}, {"source_id": "a"}])


def tiny_zip(members: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in members.items():
            archive.writestr(name, text)
    return buffer.getvalue()


def test_zip_opening_text_has_member_names_and_start_of_text_members() -> None:
    content = tiny_zip({"d/codes-x.txt": "X0001   Synthetic title\n", "d/notes.pdf": "ignored"})
    text = opening_text(content, "zip")
    assert "d/codes-x.txt" in text
    assert "Synthetic title" in text
    assert "ignored" not in text


def test_zip_garbage_raises_extraction_error() -> None:
    with pytest.raises(ExtractionError):
        opening_text(b"not a zip", "zip")


def test_data_role_zip_entry_is_verified_and_not_corpus() -> None:
    entry = parse_catalog(
        {
            "source": [
                entry_dict(
                    role="data", kind="zip", expected_phrases=["codes-x.txt", "Synthetic title"]
                )
            ]
        }
    )[0]
    assert entry.role == "data" and entry.extension == "zip"
    content = tiny_zip({"d/codes-x.txt": "X0001   Synthetic title\n"})
    row = build_row(entry, fake_result(content), Path("data/raw/x1.zip"), {})
    assert row["status"] == "VERIFIED"
    assert row["role"] == "data"
