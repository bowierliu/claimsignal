from __future__ import annotations

import json
import re
from typing import Any

from claims_copilot.project import MANIFEST_PATH

REQUIRED = {
    "source_id",
    "title",
    "publisher",
    "url",
    "retrieved_at",
    "sha256",
    "license_note",
    "status",
}
CITATION_FIELDS = {"source_id", "url", "sha256", "license_note"}
STATUSES = {"VERIFIED", "UNVERIFIED", "MISMATCH"}


def manifest_rows() -> list[dict[str, Any]]:
    return [json.loads(line) for line in MANIFEST_PATH.read_text().splitlines() if line.strip()]


def test_manifest_rows_have_required_fields_and_valid_values() -> None:
    rows = manifest_rows()
    assert rows
    for row in rows:
        missing = REQUIRED - row.keys()
        assert not missing, (row.get("source_id"), missing)
        assert row["status"] in STATUSES
        assert row["url"].startswith("https://")
        assert row["license_note"].strip()
        if row["sha256"] is None:
            # Only a source that could not be fetched may lack a hash, and it must say why.
            assert row["status"] == "UNVERIFIED", row["source_id"]
            assert row["retrieved_at"] is None
            assert row["unverified_reason"].strip()
        else:
            assert re.fullmatch(r"[0-9a-f]{64}", row["sha256"]), row["source_id"]
            assert row["retrieved_at"], row["source_id"]


def test_manifest_has_all_citation_fields() -> None:
    for row in manifest_rows():
        assert row.keys() >= CITATION_FIELDS


def test_source_ids_are_unique() -> None:
    ids = [row["source_id"] for row in manifest_rows()]
    assert len(ids) == len(set(ids))
