"""Provenance manifest (SOURCES/manifest.jsonl): one JSON object per line, sorted by source_id."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

Row = dict[str, Any]


def read_manifest(path: Path) -> list[Row]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def write_manifest(path: Path, rows: list[Row]) -> None:
    ids = [r["source_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate source_id in manifest rows")
    ordered = sorted(rows, key=lambda r: r["source_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in ordered),
        encoding="utf-8",
    )


def merge_rows(existing: list[Row], updates: list[Row]) -> list[Row]:
    """Replace rows with matching source_id; keep every other existing row untouched."""
    updated_ids = {r["source_id"] for r in updates}
    return [r for r in existing if r["source_id"] not in updated_ids] + updates
