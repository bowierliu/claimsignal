"""Every route, on a small hand-built database."""

from __future__ import annotations

from pathlib import Path

import pytest

from api_fixtures import make_client


def test_health_reports_dataset_and_optional_parts(tmp_path: Path) -> None:
    body = make_client(tmp_path).get("/v1/health").json()
    assert body["status"] == "ok" and body["dataset_hash"] == "abc123"
    assert body["claim_count"] == 3
    assert body["ruleset"].startswith("synthetic-v1")
    assert body["icd_codes"] == "fixture"
    assert (
        body["policy_search"] is True and body["policy_chunks"] == 2
    )  # the unverified chunk is not indexed


def test_health_when_icd_list_and_policy_index_are_absent(tmp_path: Path) -> None:
    body = make_client(tmp_path, policy=False, icd=False).get("/v1/health").json()
    assert body["icd_codes"] is None
    assert body["policy_search"] is False and body["policy_chunks"] == 0


def test_every_response_names_the_request_and_never_trusts_a_caller_id(tmp_path: Path) -> None:
    r = make_client(tmp_path).get("/v1/health", headers={"X-Request-ID": "caller-chosen"})
    assert r.headers["X-Request-ID"] != "caller-chosen" and len(r.headers["X-Request-ID"]) == 32
    assert r.headers["X-Dataset-Hash"] == "abc123"


def test_claim_returns_lines_modifiers_and_flags(tmp_path: Path) -> None:
    body = make_client(tmp_path).get("/v1/claims/C0000001").json()
    assert body["claim"]["claim_id"] == "C0000001"
    assert body["claim"]["total_billed"] == "100.00"  # money is text, not a float
    assert [ln["code"] for ln in body["lines"]] == ["X0010", "X0011", "X0020"]
    assert [f["flag_id"] for f in body["flags"]] == ["F000001", "F000002"]


def test_dossier_returns_all_six_results_unranked_with_the_notice(tmp_path: Path) -> None:
    body = make_client(tmp_path).get("/v1/claims/C0000001/dossier").json()
    assert [r["tool"] for r in body["results"]] == [
        "check_bundling",
        "check_unit_limits",
        "check_service_dates",
        "find_duplicate_candidates",
        "validate_claim_codes",
        "provider_intensity",
    ]
    assert body["finding_count"] == 2
    assert body["notice"] == "Findings describe the data. They are not determinations."
    assert all(r["notice"] == body["notice"] for r in body["results"])
    assert body["results"][0]["findings"][0]["refs"]  # findings point at rows
    statuses = {r["tool"]: r["status"] for r in body["results"]}
    assert statuses["check_bundling"] == "found"
    assert statuses["check_service_dates"] == "nothing_found"
    assert statuses["provider_intensity"] == "not_scored"
    for r in body["results"]:
        assert (r["status"] == "found") == bool(r["findings"])
        assert (r["status_reason"] is not None) == (r["status"] == "not_scored")


@pytest.mark.parametrize(
    ("check", "tool", "count"),
    [
        ("bundling", "check_bundling", 1),
        ("unit-limits", "check_unit_limits", 1),
        ("service-dates", "check_service_dates", 0),
        ("duplicates", "find_duplicate_candidates", 0),
        ("codes", "validate_claim_codes", 0),
    ],
)
def test_each_check_route_runs_one_tool(tmp_path: Path, check: str, tool: str, count: int) -> None:
    body = make_client(tmp_path).get(f"/v1/claims/C0000001/checks/{check}").json()
    assert body["tool"] == tool
    assert len(body["findings"]) == count
    assert body["examined"].strip()
    assert body["status"] == ("found" if count else "nothing_found")
    assert body["status_reason"] is None


def test_codes_check_says_not_checked_when_the_icd_list_is_missing(tmp_path: Path) -> None:
    body = make_client(tmp_path, icd=False).get("/v1/claims/C0000001/checks/codes").json()
    assert any("not checked" in s for s in body["limits"])


def test_member_history_is_oldest_first_and_reports_truncation(tmp_path: Path) -> None:
    c = make_client(tmp_path)
    full = c.get("/v1/members/M000001/history").json()
    assert [x["claim_id"] for x in full["claims"]] == ["C0000001", "C0000002"]
    assert full["total_claims"] == 2 and full["truncated"] is False
    short = c.get("/v1/members/M000001/history?limit=1").json()
    assert len(short["claims"]) == 1 and short["truncated"] is True


def test_provider_profile_and_intensity_and_peers(tmp_path: Path) -> None:
    c = make_client(tmp_path)
    prof = c.get("/v1/providers/P0001").json()
    assert prof["specialty"] == "primary_care" and prof["claim_count"] == 2
    assert prof["flagged_claim_count"] == 1
    inten = c.get("/v1/providers/P0001/intensity").json()
    assert inten["findings"] == [] and any("Not scored" in s for s in inten["limits"])
    assert inten["status"] == "not_scored" and inten["status_reason"]
    peers = c.get("/v1/providers/P0001/peers").json()
    assert peers["stats"] is None and peers["peers"] == [] and peers["limits"]


def test_flags_page_by_cursor(tmp_path: Path) -> None:
    c = make_client(tmp_path)
    first = c.get("/v1/flags?limit=2").json()
    assert [f["flag_id"] for f in first["flags"]] == ["F000001", "F000002"]
    assert first["truncated"] is True and first["total"] == 3
    assert first["next_after"] == "F000002"
    second = c.get(f"/v1/flags?limit=2&after={first['next_after']}").json()
    assert [f["flag_id"] for f in second["flags"]] == ["F000003"]
    assert second["truncated"] is False and second["next_after"] is None


def test_flags_filter_by_screen(tmp_path: Path) -> None:
    body = make_client(tmp_path).get("/v1/flags?screen_code=SCR02").json()
    assert [f["flag_id"] for f in body["flags"]] == ["F000002"]
    assert body["total"] == 1


def test_policy_search_returns_cited_untrusted_chunks_only_from_verified_sources(
    tmp_path: Path,
) -> None:
    body = make_client(tmp_path).get("/v1/policy/search?q=modifier").json()
    assert [h["chunk_id"] for h in body["hits"]] == ["doc-a:3-4:0000"]  # not the unverified one
    hit = body["hits"][0]
    assert hit["untrusted"] is True
    assert hit["source"] == {
        "source_id": "doc-a",
        "title": "Fixture manual",
        "url": "https://example.invalid/doc-a.pdf",
        "retrieved_at": "2026-10-16T00:00:00+00:00",
        "sha256": "a" * 64,
    }
    assert "untrusted" in body["notice"].lower() and "BM25" in body["ranking"]


def test_policy_search_with_no_matching_words_returns_no_hits(tmp_path: Path) -> None:
    assert make_client(tmp_path).get("/v1/policy/search?q=zzzz").json()["hits"] == []


def test_policy_search_says_unavailable_when_no_index(tmp_path: Path) -> None:
    r = make_client(tmp_path, policy=False).get("/v1/policy/search?q=modifier")
    assert r.status_code == 503 and r.json()["type"] == "unavailable"


@pytest.mark.parametrize(
    "url",
    [
        "/v1/policy/search",
        "/v1/policy/search?q=",
        "/v1/policy/search?q=" + "x" * 301,
        "/v1/policy/search?q=a&k=0",
        "/v1/policy/search?q=a&k=21",
    ],
)
def test_policy_search_rejects_bad_parameters(tmp_path: Path, url: str) -> None:
    assert make_client(tmp_path).get(url).status_code == 422


def test_unknown_ids_are_404_with_a_problem_body(tmp_path: Path) -> None:
    c = make_client(tmp_path)
    for url in [
        "/v1/claims/C9999999",
        "/v1/claims/C9999999/dossier",
        "/v1/claims/C9999999/checks/bundling",
        "/v1/members/M999999/history",
        "/v1/providers/P9999",
        "/v1/providers/P9999/intensity",
    ]:
        r = c.get(url)
        assert r.status_code == 404, url
        assert set(r.json()) == {"type", "title", "status", "detail", "request_id"}
        assert r.json()["type"] == "not-found"


def test_the_tool_manifest_lists_every_operation_an_agent_may_call(tmp_path: Path) -> None:
    tools = make_client(tmp_path).get("/v1/tools").json()["tools"]
    names = {t["name"] for t in tools}
    assert names == {
        "get_claim",
        "claim_dossier",
        "run_claim_check",
        "get_member_history",
        "get_provider_profile",
        "provider_intensity",
        "provider_peer_group",
        "list_flags",
        "search_policy",
    }
    check = next(t for t in tools if t["name"] == "run_claim_check")
    assert set(check["parameters"]["required"]) == {"claim_id", "check"}
    assert check["method"] == "GET" and check["path"] == "/v1/claims/{claim_id}/checks/{check}"
