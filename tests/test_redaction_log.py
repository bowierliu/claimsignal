from __future__ import annotations

import json

from claims_copilot.ingest.extract import REDACTIONS_PATH
from claims_copilot.project import MANIFEST_PATH
from claims_copilot.sources.manifest import read_manifest

ALLOWED_KEYS = {"source_id", "page", "code", "rule", "chars", "sha256"}


def test_redaction_log_holds_no_descriptor_text() -> None:
    lines = REDACTIONS_PATH.read_text(encoding="utf-8").splitlines()
    assert lines, "expected redactions for the NCCI chapters"
    for line in lines:
        entry = json.loads(line)
        assert set(entry) == ALLOWED_KEYS
        assert len(entry["sha256"]) == 64
        assert len(entry["code"]) == 5


def test_manifest_redaction_counts_match_log() -> None:
    counts: dict[str, int] = {}
    for line in REDACTIONS_PATH.read_text(encoding="utf-8").splitlines():
        sid = json.loads(line)["source_id"]
        counts[sid] = counts.get(sid, 0) + 1
    for row in read_manifest(MANIFEST_PATH):
        if row.get("role") == "corpus" and row["status"] == "VERIFIED":
            assert row["cpt_redactions"] == counts.get(row["source_id"], 0), row["source_id"]
