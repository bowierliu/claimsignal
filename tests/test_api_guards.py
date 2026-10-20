"""The API's two promises: no verdicts, no ground truth. Plus hostile input and determinism."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from api_fixtures import make_app, make_client
from claims_copilot.api.app import create_app, router
from claims_copilot.synth.config import GeneratorConfig
from claims_copilot.synth.generate import generate
from claims_copilot.synth.store import PAYER_FILE, TRUTH_FILE, write_dataset
from claims_copilot.tools.repository import RepositoryError
from tool_fixtures import VERDICT, icd_fixture

API_DIR = Path(__file__).resolve().parents[1] / "src" / "claims_copilot" / "api"
TRUTH_TOKENS = (
    "anomaly_truth",
    "truth_claim",
    "truth_line",
    "truth.sqlite",
    "load_dataset",
    "tools.score",
    "import score",
)


def test_no_api_module_reads_the_ground_truth() -> None:
    offenders = []
    for path in sorted(API_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        offenders += [f"{path.name}: {t}" for t in TRUTH_TOKENS if t in text]
    assert offenders == []


def test_the_app_refuses_to_open_the_truth_store(tmp_path: Path) -> None:
    ds = generate(GeneratorConfig.small())
    _, truth = write_dataset(ds, tmp_path)
    with pytest.raises(RepositoryError):
        create_app(truth, icd_loader=lambda: icd_fixture(), policy_loader=lambda: None)


def _strings(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [t for k, v in node.items() for t in [str(k), *_strings(v)]]
    if isinstance(node, list):
        return [t for v in node for t in _strings(v)]
    return []


@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory) -> tuple[TestClient, list[str], list[str]]:
    """The API over generated data, with a directory that holds only payer.sqlite."""
    out = tmp_path_factory.mktemp("gen")
    ds = generate(GeneratorConfig.small())
    write_dataset(ds, out)
    (out / TRUTH_FILE).unlink()  # the service must never need it
    assert sorted(p.name for p in out.iterdir()) == [PAYER_FILE]
    codes = {c for cl in ds.claims for c in cl.diagnosis_codes}
    app = create_app(
        out / PAYER_FILE, icd_loader=lambda: icd_fixture(*codes), policy_loader=lambda: None
    )
    flagged = sorted({f.claim_id for f in ds.flags})
    providers = sorted({c.provider_id for c in ds.claims if c.claim_id in flagged[:30]})
    return TestClient(app), flagged, providers


def test_the_service_runs_every_route_with_only_payer_sqlite_present(
    generated: tuple[TestClient, list[str], list[str]],
) -> None:
    client, flagged, providers = generated
    cid, pid = flagged[0], providers[0]
    claim = client.get(f"/v1/claims/{cid}").json()["claim"]
    urls = [
        "/v1/health",
        "/v1/tools",
        "/v1/flags?limit=5",
        f"/v1/claims/{cid}",
        f"/v1/claims/{cid}/dossier",
        *[
            f"/v1/claims/{cid}/checks/{c}"
            for c in ("bundling", "unit-limits", "service-dates", "duplicates", "codes")
        ],
        f"/v1/members/{claim['member_id']}/history",
        f"/v1/providers/{pid}",
        f"/v1/providers/{pid}/intensity",
        f"/v1/providers/{pid}/peers",
        "/openapi.json",
    ]
    for url in urls:
        assert client.get(url).status_code == 200, url


def test_live_responses_never_use_verdict_language(
    generated: tuple[TestClient, list[str], list[str]],
) -> None:
    client, flagged, providers = generated
    assert len(flagged) >= 20
    scanned = 0
    for cid in flagged:
        body = client.get(f"/v1/claims/{cid}/dossier").json()
        assert len(body["results"]) == 6
        for text in _strings(body):
            assert not VERDICT.search(text), (cid, text)
        scanned += 1
    for pid in providers:
        for suffix in ("", "/intensity", "/peers"):
            for text in _strings(client.get(f"/v1/providers/{pid}{suffix}").json()):
                assert not VERDICT.search(text), (pid, suffix, text)
    for text in _strings(client.get("/v1/flags?limit=200").json()):
        assert not VERDICT.search(text), text
    for text in _strings(client.get("/v1/tools").json()):
        assert not VERDICT.search(text), text
    assert scanned == len(flagged)


def test_the_dossier_has_no_combined_outcome_field(
    generated: tuple[TestClient, list[str], list[str]],
) -> None:
    client, flagged, _ = generated
    body = client.get(f"/v1/claims/{flagged[0]}/dossier").json()
    assert set(body) == {"claim", "lines", "flags", "results", "finding_count", "notice"}


HOSTILE = [
    "C1",
    "C0000001'--",
    "C0000001';DROP TABLE claim;--",
    "C" + "9" * 500,
    "%00",
    "C000000\u0661",  # an Arabic-Indic digit is not a digit here
    "\uff23\uff10\uff10\uff10\uff10\uff10\uff10\uff11",  # fullwidth letters
    "../C0000001",
    "C0000001%0a",
]


@pytest.mark.parametrize("bad", HOSTILE)
def test_hostile_path_ids_are_rejected_without_echo(tmp_path: Path, bad: str) -> None:
    client = make_client(tmp_path)
    for template in (
        "/v1/claims/{}",
        "/v1/claims/{}/dossier",
        "/v1/claims/{}/checks/bundling",
        "/v1/members/{}/history",
        "/v1/providers/{}",
        "/v1/providers/{}/peers",
    ):
        r = client.get(template.format(quote(bad, safe="")))
        assert r.status_code in (404, 422), (template, r.status_code)
        body = r.text.lower()
        if len(bad) > 4:  # a 2-character id such as "C1" can occur in the body by chance
            assert bad.lower() not in body and quote(bad, safe="").lower() not in body
        assert "traceback" not in body and "sqlite" not in body and "truth" not in body


@pytest.mark.parametrize(
    "query",
    [
        "screen_code=SCR01'%3B--",
        "screen_code=scr01",
        "limit=0",
        "limit=201",
        "limit=-1",
        "limit=1e9",
        "limit=abc",
        "after=F1",
        "after=%27%20OR%201%3D1",
    ],
)
def test_hostile_query_values_are_rejected_without_echo(tmp_path: Path, query: str) -> None:
    r = make_client(tmp_path).get(f"/v1/flags?{query}")
    assert r.status_code == 422
    value = query.split("=", 1)[1]
    # The random request id is hex and can contain a short value by chance (it did: "1e9").
    body = r.text.replace(r.json()["request_id"], "")
    assert value not in body or len(value) <= 2
    assert set(r.json()) == {"type", "title", "status", "detail", "request_id"}
    assert r.json()["detail"].startswith("Invalid: query.")


def test_other_methods_are_not_allowed(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    for method in ("post", "put", "delete", "patch"):
        r = getattr(client, method)("/v1/claims/C0000001")
        assert r.status_code == 405, method
        assert r.json()["type"] == "method-not-allowed"


def test_unexpected_errors_return_a_generic_body(tmp_path: Path) -> None:
    app = make_app(tmp_path)

    def boom() -> None:
        raise ValueError("secret detail /private/path")

    app.add_api_route("/v1/boom", boom, methods=["GET"])
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/v1/boom")
    assert r.status_code == 500
    assert "secret" not in r.text and "/private" not in r.text
    assert r.json()["detail"] == "Something went wrong."


def test_the_dataset_going_missing_is_a_generic_503(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    (tmp_path / "payer.sqlite").unlink()
    r = client.get("/v1/claims/C0000001")
    assert r.status_code == 503
    assert r.json()["detail"] == "The dataset is not available."
    assert "payer" not in r.text.lower().replace("the dataset", "")


def test_identical_requests_return_identical_bytes(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    for url in (
        "/v1/health",
        "/v1/tools",
        "/v1/claims/C0000001",
        "/v1/claims/C0000001/dossier",
        "/v1/members/M000001/history",
        "/v1/providers/P0001/peers",
        "/v1/flags",
        "/v1/policy/search?q=modifier",
        "/openapi.json",
    ):
        assert client.get(url).content == client.get(url).content, url


def test_two_separate_apps_over_the_same_data_agree(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a, b = make_client(tmp_path / "a"), make_client(tmp_path / "b")
    url = "/v1/claims/C0000001/dossier"
    assert a.get(url).content == b.get(url).content


def test_only_known_routes_exist() -> None:
    paths = {r.path for r in router.routes if isinstance(r, APIRoute)}
    assert len(paths) >= 10
    assert all(p.startswith("/v1/") for p in paths)
    # No route takes a file path, SQL text, or a free-form filter.
    assert not [p for p in paths if re.search(r"\{(path|sql|query|file)\}", p)]


def test_copying_the_database_elsewhere_does_not_change_answers(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    other = tmp_path / "elsewhere"
    other.mkdir()
    shutil.copy(tmp_path / "payer.sqlite", other / "payer.sqlite")
    again = TestClient(
        create_app(
            other / "payer.sqlite",
            icd_loader=lambda: icd_fixture("E119"),
            policy_loader=lambda: None,
        )
    )
    assert (
        client.get("/v1/claims/C0000001/dossier").json()
        == again.get("/v1/claims/C0000001/dossier").json()
    )
