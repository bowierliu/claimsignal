"""Extract page-anchored, CPT-scrubbed text from verified raw sources.

Writes data/text/<source_id>.jsonl (gitignored), one line per page:
{"source_id", "page", "text"}. Pages are 1-based physical PDF pages; XML/HTML sources are a single
page 1. Only sources whose manifest status is VERIFIED are extracted.

Also writes SOURCES/redactions.jsonl (committed): one line per CPT descriptor removed, holding
only code, page, rule, length and a hash, never descriptor text. Each manifest row gets
`cpt_redactions` (count) so the provenance record shows what was changed.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from claims_copilot.ingest.scrub import Redaction, scrub
from claims_copilot.project import MANIFEST_PATH, REPO_ROOT, SOURCES_DIR, TEXT_DIR
from claims_copilot.sources.manifest import Row, merge_rows, read_manifest, write_manifest
from claims_copilot.sources.verify import markup_to_text, pdf_pages

REDACTIONS_PATH = SOURCES_DIR / "redactions.jsonl"


def extract_source(
    row: Row, repo_root: Path = REPO_ROOT
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    raw = (repo_root / row["local_path"]).read_bytes()
    texts = pdf_pages(raw) if row["kind"] == "pdf" else [markup_to_text(raw)]
    pages: list[dict[str, object]] = []
    log: list[dict[str, object]] = []
    for number, text in enumerate(texts, start=1):
        clean, redactions = scrub(text)
        pages.append({"source_id": row["source_id"], "page": number, "text": clean})
        log.extend(_log_entry(row["source_id"], number, r) for r in redactions)
    return pages, log


def _log_entry(source_id: str, page: int, r: Redaction) -> dict[str, object]:
    return {"source_id": source_id, "page": page, **asdict(r)}


def run() -> None:
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(MANIFEST_PATH)
    updated: list[Row] = []
    all_log: list[dict[str, object]] = []
    for row in manifest:
        if row.get("role") != "corpus" or row["status"] != "VERIFIED":
            continue
        pages, log = extract_source(row)
        (TEXT_DIR / f"{row['source_id']}.jsonl").write_text(
            "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in pages), encoding="utf-8"
        )
        all_log.extend(log)
        updated.append({**row, "cpt_redactions": len(log)})
        chars = sum(len(str(p["text"])) for p in pages)
        print(
            f"{row['source_id']:<26} pages={len(pages):>4} chars={chars:>9} redacted={len(log):>3}"
        )
    REDACTIONS_PATH.write_text(
        "".join(json.dumps(e, sort_keys=True) + "\n" for e in all_log), encoding="utf-8"
    )
    write_manifest(MANIFEST_PATH, merge_rows(manifest, updated))


if __name__ == "__main__":
    run()
