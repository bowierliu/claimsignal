"""Fetch every catalog source, verify identity, and write manifest rows.

Run: `uv run python -m claims_copilot.sources.fetch [source_id ...]`
Raw files go to data/raw/ (gitignored). Responses are cached under data/cache/, so a re-run
reuses the original retrieved_at timestamps and hashes unless the cache is deleted.
"""

from __future__ import annotations

import sys
from pathlib import Path

from claims_copilot.project import CACHE_DIR, CATALOG_PATH, MANIFEST_PATH, RAW_DIR
from claims_copilot.sources.catalog import CatalogEntry, load_catalog
from claims_copilot.sources.http import FetchError, FetchResult, HttpClient
from claims_copilot.sources.manifest import Row, merge_rows, read_manifest, write_manifest
from claims_copilot.sources.verify import (
    ExtractionError,
    contains_quote,
    full_text,
    missing_phrases,
    opening_text,
)

CPT_CAVEAT = (
    "Document may reference third-party content such as AMA CPT; any CPT descriptor text is "
    "redacted at ingest and logged."
)


def build_row(
    entry: CatalogEntry, result: FetchResult, local_path: Path, terms: dict[str, Row]
) -> Row:
    row: Row = {
        "source_id": entry.source_id,
        "role": entry.role,
        "group": entry.group,
        "title": entry.title,
        "publisher": entry.publisher,
        "url": entry.url,
        "final_url": result.final_url,
        "kind": entry.kind,
        "version": entry.version,
        "retrieved_at": result.retrieved_at,
        "http_status": result.status,
        "content_type": result.content_type,
        "sha256": result.sha256,
        "bytes": len(result.content),
        "local_path": str(local_path),
        "terms_source_id": entry.terms_source_id,
        "expected_phrases": list(entry.expected_phrases),
    }
    try:
        # Terms pages are matched against the whole page; corpus documents against their opening.
        text_for_quote = full_text(result.content, entry.kind) if entry.role == "terms" else ""
        identity_text = text_for_quote or opening_text(result.content, entry.kind)
        missing = missing_phrases(identity_text, entry.expected_phrases)
    except ExtractionError as exc:
        row.update(status="UNVERIFIED", unverified_reason=f"text extraction failed: {exc}")
        row["license_note"] = _license_note(entry, terms)
        row["terms_status"] = "UNVERIFIED"
        return row

    if missing:
        row.update(status="MISMATCH", missing_phrases=missing)
    else:
        row["status"] = "VERIFIED"

    if entry.role == "terms":
        observed = entry.terms_status == "OBSERVED" and contains_quote(
            text_for_quote, entry.terms_quote
        )
        row["terms_status"] = "OBSERVED" if observed else "UNVERIFIED"
        row["terms_quote"] = entry.terms_quote if observed else ""
        row["license_note"] = (
            f'Publisher statement: "{entry.terms_quote}"'
            if observed
            else "No copyright or reuse statement found on this page."
        )
    else:
        row["license_note"] = _license_note(entry, terms)
        terms_row = terms.get(entry.terms_source_id)
        row["terms_status"] = terms_row["terms_status"] if terms_row else "UNVERIFIED"
    return row


def _license_note(entry: CatalogEntry, terms: dict[str, Row]) -> str:
    terms_row = terms.get(entry.terms_source_id)
    if terms_row and terms_row.get("terms_status") == "OBSERVED":
        note = (
            f'{terms_row["publisher"]} states: "{terms_row["terms_quote"]}" '
            f"(manifest: {entry.terms_source_id})."
        )
        return f"{note} {CPT_CAVEAT}" if entry.publisher == "CMS" else note
    return (
        "Terms UNVERIFIED: no readable reuse statement found. Treated as a US government work "
        "for local use only; raw file is gitignored and never redistributed."
    )


def failure_row(entry: CatalogEntry, reason: str) -> Row:
    return {
        "source_id": entry.source_id,
        "role": entry.role,
        "group": entry.group,
        "title": entry.title,
        "publisher": entry.publisher,
        "url": entry.url,
        "kind": entry.kind,
        "version": entry.version,
        "retrieved_at": None,
        "sha256": None,
        "status": "UNVERIFIED",
        "unverified_reason": reason,
        "license_note": "Not fetched; terms not assessed.",
        "terms_status": "UNVERIFIED",
    }


def run(only: set[str] | None = None) -> int:
    entries = [e for e in load_catalog(CATALOG_PATH) if not only or e.source_id in only]
    entries.sort(key=lambda e: e.role != "terms")  # terms first: corpus rows cite them
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    client = HttpClient(CACHE_DIR)
    terms: dict[str, Row] = {}
    rows: list[Row] = []
    try:
        for entry in entries:
            try:
                result = client.get(entry.url)
            except FetchError as exc:
                row = failure_row(entry, str(exc))
            else:
                local_path = RAW_DIR / f"{entry.source_id}.{entry.extension}"
                local_path.write_bytes(result.content)
                row = build_row(entry, result, local_path.relative_to(RAW_DIR.parents[1]), terms)
            if entry.role == "terms":
                terms[entry.source_id] = row
            rows.append(row)
            tag = row["status"] + (
                "" if not row.get("missing_phrases") else f" missing={row['missing_phrases']}"
            )
            digest = (row["sha256"] or "-")[:12]
            print(f"{entry.source_id:<26} {tag:<12} {row.get('bytes', 0):>10} {digest}")
    finally:
        client.close()
    write_manifest(MANIFEST_PATH, merge_rows(read_manifest(MANIFEST_PATH), rows))
    return 0 if all(r["status"] == "VERIFIED" for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(run(set(sys.argv[1:]) or None))
