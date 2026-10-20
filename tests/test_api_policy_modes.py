"""Policy search modes: default lexical, opt-in hybrid, and a visible fallback."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from api_fixtures import SOURCE, build_db, chunk
from claims_copilot.api.app import create_app
from claims_copilot.api.policy import PolicyIndex
from claims_copilot.retrieval.bm25 import Hit
from claims_copilot.retrieval.pipeline import PipelineResult, PipelineUnavailableError
from tool_fixtures import icd_fixture

CHUNKS = [
    chunk("doc-a:3-4:0000", "doc-a", "Modifier 59 marks a distinct procedural service."),
    chunk("doc-a:3-4:0001", "doc-a", "Units of service are counted per line."),
    chunk("unverified:1-1:0000", "unverified", "not a manifest source"),
]


class FakeHybrid:
    def __init__(self, result: PipelineResult | Exception) -> None:
        self.result = result
        self.queries: list[str] = []

    def search(self, query: str, k: int) -> PipelineResult:
        self.queries.append(query)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _client(tmp_path: Path, index: PolicyIndex) -> TestClient:
    path = build_db(tmp_path / "payer.sqlite")
    app = create_app(path, icd_loader=lambda: icd_fixture("E119"), policy_loader=lambda: index)
    return TestClient(app)


def test_default_is_lexical_with_scores_and_no_fallback(tmp_path: Path) -> None:
    body = (
        _client(tmp_path, PolicyIndex(CHUNKS, {"doc-a": SOURCE}))
        .get("/v1/policy/search?q=modifier")
        .json()
    )
    assert body["mode"] == "lexical" and body["fallback_reason"] is None
    assert isinstance(body["hits"][0]["bm25"], float)


def test_hybrid_results_are_served_without_a_lexical_score(tmp_path: Path) -> None:
    fake = FakeHybrid(PipelineResult([Hit("doc-a:3-4:0001", 0.1)], "hybrid_rerank"))
    index = PolicyIndex(CHUNKS, {"doc-a": SOURCE}, hybrid=fake)
    body = _client(tmp_path, index).get("/v1/policy/search?q=how+many+units").json()
    assert fake.queries == ["how many units"]
    assert body["mode"] == "hybrid_rerank" and body["fallback_reason"] is None
    assert [h["chunk_id"] for h in body["hits"]] == ["doc-a:3-4:0001"]
    assert body["hits"][0]["bm25"] is None and body["hits"][0]["untrusted"] is True
    assert "reordered" in body["ranking"]


def test_hybrid_never_serves_a_chunk_from_an_unverified_source(tmp_path: Path) -> None:
    fake = FakeHybrid(
        PipelineResult([Hit("unverified:1-1:0000", 1.0), Hit("doc-a:3-4:0000", 0.5)], "hybrid")
    )
    index = PolicyIndex(CHUNKS, {"doc-a": SOURCE}, hybrid=fake)
    body = _client(tmp_path, index).get("/v1/policy/search?q=anything").json()
    assert [h["chunk_id"] for h in body["hits"]] == ["doc-a:3-4:0000"]


def test_a_failing_hybrid_pipeline_falls_back_to_lexical_and_says_so(tmp_path: Path) -> None:
    fake = FakeHybrid(PipelineUnavailableError("spend cap reached"))
    index = PolicyIndex(CHUNKS, {"doc-a": SOURCE}, hybrid=fake)
    body = _client(tmp_path, index).get("/v1/policy/search?q=modifier").json()
    assert body["mode"] == "lexical"
    assert "spend cap reached" in body["fallback_reason"]
    assert [h["chunk_id"] for h in body["hits"]] == ["doc-a:3-4:0000"]


def test_hybrid_that_could_not_load_says_why_on_every_response(tmp_path: Path) -> None:
    index = PolicyIndex(
        CHUNKS,
        {"doc-a": SOURCE},
        hybrid_unavailable="hybrid search unavailable (OPENAI_API_KEY is not set); lexical "
        "results shown",
    )
    body = _client(tmp_path, index).get("/v1/policy/search?q=modifier").json()
    assert body["mode"] == "lexical" and "OPENAI_API_KEY" in body["fallback_reason"]
