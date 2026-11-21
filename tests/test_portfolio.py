"""Recorded artifacts, guarded HTTP investigations and refusal paths, entirely offline."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from claims_copilot.api.__main__ import main as legacy
from claims_copilot.evals.handbuilt import build_handbuilt
from claims_copilot.portfolio import CASES, replay_asset
from claims_copilot.portfolio_guard import MODEL, Guard, initialize
from claims_copilot.portfolio_server import ASSETS, ORIGIN, create_app
from claims_copilot.project import REPO_ROOT

HEADERS = {"Origin": ORIGIN, "X-Demo-Request": "investigate"}


@pytest.fixture
def payer(tmp_path: Path) -> Path:
    path = tmp_path / "payer.sqlite"
    build_handbuilt(path)
    return path


@pytest.fixture
def client(payer: Path) -> TestClient:
    return TestClient(create_app(payer), base_url=ORIGIN)


def test_replays_match_offline_tools_and_only_demo_assets_served(
    payer: Path, client: TestClient
) -> None:
    assert replay_asset(payer) == (REPO_ROOT / "docs/demo/cases.js").read_text()
    assert client.get("/api/status").json() == {"service": "claims-portfolio-v1"}
    assert client.get("/").status_code == 200
    for name in ASSETS:
        assert client.get(f"/demo/{name}").status_code == 200
    for path in ["/eval/labeling", "/demo/portfolio_guard.py", "/portfolio_guard.py", "/admin"]:
        assert client.get(path).status_code == 404


def test_foreign_origins_and_unsupported_requests_do_not_reach_guard(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Guard, "from_env", lambda: pytest.fail("guard should not be invoked"))
    route = "/api/investigations/units"
    for headers in [{}, {"Origin": ORIGIN}, {**HEADERS, "Origin": "https://example.org"}]:
        assert client.post(route, headers=headers).status_code == 403
    assert client.post(route, headers={**HEADERS, "Host": "example.org"}).status_code == 400
    assert client.post(route, headers=HEADERS, json={"model": "custom"}).status_code == 400
    assert client.post(route + "?user=new", headers=HEADERS).status_code == 400
    assert client.post("/api/investigations/unknown", headers=HEADERS).status_code == 404


def install_guard(
    path: Path, monkeypatch: pytest.MonkeyPatch, answers: list[str]
) -> list[dict[str, Any]]:
    initialize(path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE settings SET value = 1 WHERE name = 'enabled'")
    sent: list[dict[str, Any]] = []

    def provider(action: str, key: str, data: dict[str, Any], timeout: float) -> dict[str, Any]:
        if action == "count":
            return {"input_tokens": 80}
        sent.append(data)
        return {
            "model": MODEL,
            "service_tier": "default",
            "status": "completed",
            "usage": {"input_tokens": 80, "output_tokens": 12},
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": answers.pop(0)}]}
            ],
        }

    guard = Guard(path, lambda: "mock", provider)
    monkeypatch.setattr(Guard, "from_env", lambda: guard)
    return sent


@pytest.mark.parametrize("key", CASES)
def test_mocked_live_http_runs_two_tools_and_two_model_calls(
    key: str, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = CASES[key]
    ledger = tmp_path / "ledger"
    sent = install_guard(
        ledger, monkeypatch, [json.dumps({"check": case.check}), '{"evidence":"E1"}']
    )
    response = client.post(f"/api/investigations/{key}", headers=HEADERS)
    assert response.status_code == 200
    output = response.json()
    assert output["mode"] == "live"
    assert output["dossier"]["claim"] == case.claim
    first, second = (json.loads(message["input"]) for message in sent)
    assert "checks" in first and "tool_result" not in first
    assert output["result"] == second["tool_result"]
    assert output["result"]["evidence"][0]["id"] == "E1"
    with sqlite3.connect(ledger) as db:
        row = db.execute("SELECT identity, active, tools FROM runs").fetchone()
    assert row == (hashlib.sha256(b"local-owner").hexdigest(), 0, 2)


@pytest.mark.parametrize(
    "answers",
    [
        ['{"check":"units"}', '{"evidence":"invented"}'],
        ['{"check":"bundle"}'],
        ['{"check":"units","extra":"untrusted verdict"}'],
        ['{"check":"units"}', "untrusted verdict"],
        ["[]"],
    ],
)
def test_ungrounded_or_out_of_scope_model_text_is_withheld(
    answers: list[str], client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_guard(tmp_path / "ledger", monkeypatch, answers.copy())
    response = client.post("/api/investigations/units", headers=HEADERS)
    assert response.status_code == 422
    assert set(response.json()) == {"error"}
    assert "withheld" in response.text
    assert "untrusted verdict" not in response.text


def test_http_fails_closed_when_ledger_missing(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Guard, "from_env", lambda: Guard(tmp_path / "missing"))
    response = client.post("/api/investigations/units", headers=HEADERS)
    assert response.status_code == 503
    assert set(response.json()) == {"error"}


@pytest.mark.parametrize(
    "args",
    [
        ["--ask", "--ask-provider", "anthropic"],
        ["--policy-mode", "hybrid"],
        ["--ask", "--record-runs"],
    ],
)
def test_research_server_cannot_serve_paid_routes(
    args: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("claims_copilot.api.__main__.get_secret", lambda _name: None)
    with pytest.raises(SystemExit) as exc:
        legacy(args)
    assert exc.value.code == 2


def test_original_freeform_workbench_uses_durable_model_and_tool_limits(
    tmp_path: Path, payer: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from claims_copilot.agent.portfolio_ask import build_portfolio_ask
    from claims_copilot.api.app import create_app as original_workbench

    scratch = tmp_path / "session"
    ledger = tmp_path / "ledger"
    text = "Line 1 records 5 units of X0030."
    answers = [
        '{"tool":"run_claim_check","arguments":{"check":"unit-limits","claim_id":"C9000004"}}',
        json.dumps(
            {
                "status": "ANSWERED",
                "reason": "SUPPORTED",
                "summary": [{"text": text, "citations": ["E1.f1"]}],
                "policy_quotes": [],
                "searched": [],
            }
        ),
    ]
    sent = install_guard(ledger, monkeypatch, answers)
    service = build_portfolio_ask(payer, scratch)
    client = TestClient(original_workbench(payer, ask=service), base_url="http://127.0.0.1:8000")
    question = {"question": "Which units are recorded on C9000004?"}
    route = "/workbench/ask"
    result = client.post(route, json=question).json()
    assert result["status"] == "ANSWERED", result
    assert result["statements"][0]["text"] == text
    assert len(sent) == 2
    assert "run_claim_check" in sent[1]["input"]
    assert result["run"]["tool_calls"] == 1
    assert result["session"]["token"]
    with sqlite3.connect(ledger) as db:
        assert db.execute("SELECT tools, active FROM runs").fetchone() == (1, 0)
        assert db.execute("SELECT count(*) FROM calls").fetchone()[0] == 2
    separate = dict(
        question, question="Should I deny this claim?", session=result["session"]["token"]
    )
    assert client.post(route, json=separate).json()["status"] == "OUT_OF_SCOPE"
    with sqlite3.connect(ledger) as db:
        db.execute("UPDATE settings SET value=0 WHERE name='enabled'")
    assert client.post(route, json=question).status_code == 503
    assert len(sent) == 2


def test_freeform_ask_does_not_forward_personal_information(
    tmp_path: Path, payer: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from claims_copilot.agent.portfolio_ask import build_portfolio_ask
    from claims_copilot.portfolio_guard import GuardError

    sent = install_guard(tmp_path / "ledger", monkeypatch, [])
    service = build_portfolio_ask(payer, tmp_path / "session")
    with pytest.raises(GuardError, match="personal information"):
        service.ask(None, "Can you send to researcher@example.invalid?", None)
    assert sent == []
