"""A small hand-built API for tests: three claims, flags, and a two-chunk policy index."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from claims_copilot.api.app import create_app
from claims_copilot.api.policy import PolicyIndex, SourceRef
from claims_copilot.ingest.chunk import Chunk
from tool_fixtures import Db, L, icd_fixture

SOURCE = SourceRef(
    source_id="doc-a",
    title="Fixture manual",
    url="https://example.invalid/doc-a.pdf",
    retrieved_at="2026-10-16T00:00:00+00:00",
    sha256="a" * 64,
)


def chunk(chunk_id: str, source_id: str, text: str) -> Chunk:
    return Chunk(chunk_id, source_id, 3, 4, "", text, "b" * 64)


def policy_index() -> PolicyIndex:
    chunks = [
        chunk("doc-a:3-4:0000", "doc-a", "Modifier 59 marks a distinct procedural service."),
        chunk("doc-a:3-4:0001", "doc-a", "Units of service are counted per line."),
        # Not in the manifest, so it must never be indexed or served.
        chunk("unverified:1-1:0000", "unverified", "modifier modifier modifier"),
    ]
    return PolicyIndex(chunks, {"doc-a": SOURCE})


def build_db(path: Path) -> Path:
    db = Db(path)
    db.claim("C0000001", [L("X0010"), L("X0011"), L("X0020", units=5)])
    db.claim("C0000002", [L("X0001")], member="M000001", start="2026-11-09")
    db.claim("C0000003", [L("X0001")], member="M000002", provider="P0002", start="2026-11-10")
    db.flag("F000001", "C0000001", "SCR01")
    db.flag("F000002", "C0000001", "SCR02")
    db.flag("F000003", "C0000003", "SCR01")
    db.con.execute("INSERT INTO meta VALUES ('payer_hash', 'abc123')")
    db.con.commit()
    return path


def make_app(tmp_path: Path, *, policy: bool = True, icd: bool = True) -> FastAPI:
    from claims_copilot.tools.icd import IcdSourceUnavailableError

    path = build_db(tmp_path / "payer.sqlite")

    def load_icd():  # type: ignore[no-untyped-def]
        if not icd:
            raise IcdSourceUnavailableError("absent")
        return icd_fixture("E119")

    return create_app(
        path, icd_loader=load_icd, policy_loader=lambda: policy_index() if policy else None
    )


def make_client(tmp_path: Path, **kw: bool) -> TestClient:
    return TestClient(make_app(tmp_path, **kw))
