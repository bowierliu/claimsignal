"""The /workbench/ask routes (spec items 5 and 9): auth, same-origin JSON only, rate limit, off
switch, headers, request validation, and absence from the public contract. No model calls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ask_fixtures import (
    DOSSIER,
    TEST_KEY,
    UNIT_FINDING,
    FakeBackend,
    answered,
    make_api,
    make_service,
    scripted,
)
from claims_copilot.agent.session import SessionStore
from claims_copilot.api.guard import API_KEY_HEADER
from claims_copilot.project import REPO_ROOT

AUTH = {API_KEY_HEADER: TEST_KEY}
BODY = {"question": "What did the checks find on claim C0000001?", "claim_id": "C0000001"}


def client_for(tmp_path: Path, backend: Any, *, key: str | None = TEST_KEY) -> TestClient:
    return TestClient(make_api(tmp_path, backend, key=key))


def post(client: TestClient, path: str = "/workbench/ask", **kw: Any) -> Any:
    headers = {**AUTH, **kw.pop("headers", {})}
    return client.post(path, headers=headers, **kw)


# ---- auth ------------------------------------------------------------------------------------


def test_ask_without_the_key_is_401_while_static_files_stay_open(tmp_path: Path) -> None:
    backend = FakeBackend()
    client = client_for(tmp_path, backend)
    assert client.post("/workbench/ask", json=BODY).status_code == 401
    assert client.post("/workbench/ask/reset", json={}).status_code == 401
    assert client.get("/workbench/ask/status").status_code == 401
    wrong = client.post("/workbench/ask", json=BODY, headers={API_KEY_HEADER: "wrong-value"})
    assert wrong.status_code == 401
    assert backend.asks == [] and backend.resets == []
    assert client.get("/workbench/app.js").status_code == 200
    assert client.get("/workbench/").status_code == 200


def test_ask_with_the_key_reaches_the_backend(tmp_path: Path) -> None:
    backend = FakeBackend()
    client = client_for(tmp_path, backend)
    response = post(client, json=BODY)
    assert response.status_code == 200
    assert backend.asks == [(None, BODY["question"], "C0000001")]
    assert client.get("/workbench/ask/status", headers=AUTH).json()["enabled"] is True


# ---- same-origin JSON only -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("content", "media"),
    [
        (json.dumps(BODY), "text/plain"),
        ("question=What+did+the+checks+find", "application/x-www-form-urlencoded"),
        (json.dumps(BODY), "multipart/form-data; boundary=x"),
    ],
)
def test_a_non_json_body_is_rejected_and_nothing_is_called(
    tmp_path: Path, content: str, media: str
) -> None:
    backend = FakeBackend()
    client = client_for(tmp_path, backend)
    response = post(client, content=content, headers={"Content-Type": media})
    assert response.status_code in (415, 422)
    assert backend.asks == []


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Sec-Fetch-Site": "cross-site"},
        {"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"},
    ],
)
def test_a_cross_site_request_is_403_and_nothing_is_called(
    tmp_path: Path, headers: dict[str, str]
) -> None:
    backend = FakeBackend()
    client = client_for(tmp_path, backend)
    assert post(client, json=BODY, headers=headers).status_code == 403
    assert post(client, "/workbench/ask/reset", json={}, headers=headers).status_code == 403
    assert backend.asks == [] and backend.resets == []


def test_a_same_origin_request_is_accepted(tmp_path: Path) -> None:
    backend = FakeBackend()
    client = client_for(tmp_path, backend)
    headers = {"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"}
    assert post(client, json=BODY, headers=headers).status_code == 200
    assert len(backend.asks) == 1


def test_a_burst_of_asks_is_rate_limited(tmp_path: Path) -> None:
    backend = FakeBackend()
    client = client_for(tmp_path, backend)
    statuses = [post(client, json=BODY).status_code for _ in range(10)]
    assert 429 in statuses
    assert len(backend.asks) == statuses.count(200) < 10
    limited = post(client, json=BODY)
    assert limited.status_code == 429 and limited.headers.get("Retry-After")


# ---- off switch, busy, headers ---------------------------------------------------------------


def test_with_ask_off_status_says_disabled_and_post_is_503(tmp_path: Path) -> None:
    client = client_for(tmp_path, None)
    status = client.get("/workbench/ask/status", headers=AUTH)
    assert status.status_code == 200 and status.json()["enabled"] is False
    assert post(client, json=BODY).status_code == 503


def test_a_busy_backend_maps_to_409(tmp_path: Path) -> None:
    client = client_for(tmp_path, FakeBackend(busy=True))
    assert post(client, json=BODY).status_code == 409


def test_a_busy_session_in_the_real_service_maps_to_409(tmp_path: Path) -> None:
    store = SessionStore()
    session, _ = store.get_or_create(None)
    provider = scripted([DOSSIER], answered("Line 3 bills 5 units.", [UNIT_FINDING]))
    service = make_service(tmp_path, provider, store=store)
    client = client_for(tmp_path, service)
    assert store.try_begin(session)
    response = post(client, json={**BODY, "session": session.token})
    assert response.status_code == 409
    assert provider.requests == []
    store.end(session)
    ok = post(client, json={**BODY, "session": session.token})
    assert ok.status_code == 200 and ok.json()["status"] == "ANSWERED"


@pytest.mark.parametrize("backend_on", [True, False])
def test_responses_carry_csp_and_no_store(tmp_path: Path, backend_on: bool) -> None:
    client = client_for(tmp_path, FakeBackend() if backend_on else None)
    responses = [
        post(client, json=BODY),
        client.get("/workbench/ask/status", headers=AUTH),
        post(client, "/workbench/ask/reset", json={}),
        post(client, json=BODY, headers={"Sec-Fetch-Site": "cross-site"}),
    ]
    for response in responses:
        assert "default-src 'none'" in response.headers.get("Content-Security-Policy", "")
        assert response.headers.get("Cache-Control") == "no-store"


def test_refusals_before_the_route_also_carry_csp_and_no_store(tmp_path: Path) -> None:
    client = client_for(tmp_path, FakeBackend())
    responses = [
        client.post("/workbench/ask", json=BODY),  # 401
        post(client, json={"question": ""}),  # 422
    ]
    for response in responses:
        assert "default-src 'none'" in response.headers.get("Content-Security-Policy", "")
        assert response.headers.get("Cache-Control") == "no-store"


# ---- contract and validation -----------------------------------------------------------------


def test_no_ask_route_is_in_the_openapi_contract(tmp_path: Path) -> None:
    client = client_for(tmp_path, FakeBackend())
    response = client.get("/openapi.json", headers=AUTH)
    schema = response.json() if response.status_code == 200 else client.app.openapi()  # type: ignore[attr-defined]
    assert not [p for p in schema["paths"] if p.startswith("/workbench")]
    committed = json.loads((REPO_ROOT / "docs" / "openapi.json").read_text(encoding="utf-8"))
    assert not [p for p in committed["paths"] if p.startswith("/workbench")]


@pytest.mark.parametrize(
    "body",
    [
        {"question": "What flags?", "claim_id": "C123"},
        {"question": "What flags?", "claim_id": "c0000001"},
        {"question": "What flags?", "claim_id": "C00000012"},
        {"question": "What flags?", "claim_id": "X0000001"},
        {"question": "What flags?", "claim_id": "C000000l"},
        {"question": "q" * 1001},
        {"question": ""},
        {"question": "What flags?", "extra": "field"},
        {"question": "What flags?", "session": "../../etc/passwd"},
        {},
    ],
)
def test_request_validation_rejects_bad_bodies(tmp_path: Path, body: dict[str, Any]) -> None:
    backend = FakeBackend()
    client = client_for(tmp_path, backend)
    assert post(client, json=body).status_code == 422
    assert backend.asks == []


def test_a_question_of_exactly_1000_characters_is_accepted(tmp_path: Path) -> None:
    backend = FakeBackend()
    client = client_for(tmp_path, backend)
    assert post(client, json={"question": "q" * 1000}).status_code == 200
    assert len(backend.asks) == 1
