"""The published contract: models match the tool records, names state no conclusions, the
manifest matches the routes, and `docs/openapi.json` matches the live schema."""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel

from api_fixtures import make_app
from claims_copilot.api import schemas as s
from claims_copilot.api.app import app_without_data, router, tool_manifest
from claims_copilot.api.snapshot import SNAPSHOT_PATH, render
from claims_copilot.tools.dossier import Dossier
from claims_copilot.tools.lookups import ClaimRecord, FlagQueue, MemberHistory, ProviderProfile
from claims_copilot.tools.patterns import PeerGroupReport, PeerRow, PeerStats
from claims_copilot.tools.records import Finding, Ref, ToolResult
from claims_copilot.tools.repository import ClaimRow, FlagRow, LineRow, ProviderRow
from tool_fixtures import VERDICT


def _names(dc: type) -> set[str]:
    return {f.name for f in fields(dc)}


def _model(m: type[BaseModel]) -> set[str]:
    return set(m.model_fields)


# (dataclass, model, fields the model does not carry as such, fields it adds)
PAIRS: list[tuple[type, type[BaseModel], set[str], set[str]]] = [
    (Ref, s.RefOut, set(), set()),
    (Finding, s.FindingOut, set(), set()),
    (ToolResult, s.ToolResultOut, set(), {"notice", "status"}),
    (ClaimRow, s.ClaimOut, set(), set()),
    (LineRow, s.LineOut, set(), set()),
    (FlagRow, s.FlagOut, set(), set()),
    (ClaimRecord, s.ClaimResponse, set(), set()),
    (Dossier, s.DossierOut, {"record"}, {"claim", "lines", "flags", "finding_count", "notice"}),
    (MemberHistory, s.MemberHistoryOut, set(), set()),
    (
        ProviderProfile,
        s.ProviderProfileOut,
        {"provider"},
        _names(ProviderRow),  # the provider row is flattened into the profile
    ),
    (PeerStats, s.PeerStatsOut, set(), {"elevated_fraction"}),
    (PeerRow, s.PeerRowOut, {"score"}, {"modified_z"}),
    (PeerGroupReport, s.PeerGroupOut, set(), {"notice"}),
    (FlagQueue, s.FlagQueueOut, set(), set()),
]


@pytest.mark.parametrize(
    ("dc", "model", "dropped", "added"), PAIRS, ids=[p[1].__name__ for p in PAIRS]
)
def test_every_record_field_has_a_model_field_and_the_reverse(
    dc: type, model: type[BaseModel], dropped: set[str], added: set[str]
) -> None:
    assert (_names(dc) - dropped) | added == _model(model)


def _walk(node: Any, path: str = "") -> list[tuple[str, str]]:
    """Every property name in a schema document, with where it was found."""
    out: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                out += [(name, path) for name in value]
            out += _walk(value, f"{path}/{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            out += _walk(value, f"{path}[{i}]")
    return out


def test_no_response_or_parameter_is_named_for_a_conclusion() -> None:
    schema = app_without_data().openapi()
    names = [n for n, _ in _walk(schema["components"])]
    for methods in schema["paths"].values():
        for op in methods.values():
            names += [p["name"] for p in op.get("parameters", [])]
    assert names
    assert {n.lower() for n in names} & s.FORBIDDEN_FIELD_NAMES == set()


def test_the_name_scan_would_catch_a_conclusion_field() -> None:
    class Bad(BaseModel):
        verdict: str

    assert {n for n, _ in _walk({"components": Bad.model_json_schema()})} & s.FORBIDDEN_FIELD_NAMES


def test_tool_descriptions_use_no_verdict_language() -> None:
    schema = app_without_data().openapi()
    for path, methods in schema["paths"].items():
        for op in methods.values():
            text = f"{op.get('summary', '')} {op.get('description', '')}"
            assert not VERDICT.search(text), (path, text)
    for model in (s.NOTICE, s.UNTRUSTED_NOTICE):
        assert not VERDICT.search(model)


def test_every_route_is_a_get() -> None:
    api_routes = [r for r in router.routes if isinstance(r, APIRoute)]
    assert len(api_routes) >= 10  # the scan is not vacuous
    assert {m for r in api_routes for m in (r.methods or set())} == {"GET"}
    schema = app_without_data().openapi()
    assert {m for methods in schema["paths"].values() for m in methods} == {"get"}
    # The app's own routes (schema and docs pages) are read-only too, except the two "Ask the
    # agent" POST routes (owner decision 2026-11-15): outside the schema, guarded, same-origin JSON.
    ask_posts = {"/workbench/ask", "/workbench/ask/reset"}
    own = [r for r in app_without_data().routes if getattr(r, "methods", None)]
    posts = {r.path for r in own if not set(r.methods) <= {"GET", "HEAD"}}  # type: ignore[attr-defined]
    assert own and posts == ask_posts
    assert all(set(r.methods) == {"POST"} for r in own if r.path in ask_posts)  # type: ignore[attr-defined]
    assert not ask_posts & set(schema["paths"])


def test_manifest_matches_the_routes_and_their_parameters(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    schema = app.openapi()
    manifest = tool_manifest(schema)
    routes = {r.path: r for r in router.routes if isinstance(r, APIRoute)}
    assert routes
    assert len({t.name for t in manifest.tools}) == len(manifest.tools)
    for tool in manifest.tools:
        route = routes[tool.path]
        assert route.operation_id == tool.name
        declared = {p["name"] for p in schema["paths"][tool.path]["get"].get("parameters", [])}
        assert set(tool.parameters["properties"]) == declared  # type: ignore[call-overload]
        assert tool.returns in schema["components"]["schemas"]
        assert tool.description.strip()
    marked = {
        op["operationId"]
        for methods in schema["paths"].values()
        for op in methods.values()
        if op.get("x-tool")
    }
    assert marked == {t.name for t in manifest.tools}
    # Health and the manifest itself are not tools.
    assert not {"health_check", "list_tools"} & marked


def test_every_id_parameter_publishes_its_pattern() -> None:
    schema = app_without_data().openapi()

    def pattern(schema: dict[str, Any]) -> str | None:
        options = [schema, *schema.get("anyOf", [])]  # optional parameters nest their schema
        return next((o["pattern"] for o in options if "pattern" in o), None)

    patterns = {
        p["name"]: pattern(p["schema"])
        for methods in schema["paths"].values()
        for op in methods.values()
        for p in op.get("parameters", [])
        if p["name"].endswith("_id") or p["name"] in {"after", "screen_code"}
    }
    assert patterns and all(patterns.values()), patterns


def test_the_error_body_replaces_the_default_validation_schema() -> None:
    schema = app_without_data().openapi()
    comps = schema["components"]["schemas"]
    assert "Problem" in comps and "HTTPValidationError" not in comps
    ref = schema["paths"]["/v1/claims/{claim_id}"]["get"]["responses"]["422"]
    assert ref["content"]["application/json"]["schema"]["$ref"].endswith("/Problem")


def test_the_committed_openapi_snapshot_is_current() -> None:
    assert SNAPSHOT_PATH.read_text(encoding="utf-8") == render(), (
        "docs/openapi.json is stale: run `uv run python -m claims_copilot.api.snapshot` and "
        "review the diff"
    )


def test_the_running_app_publishes_the_same_schema_as_the_snapshot(tmp_path: Path) -> None:
    live = json.dumps(make_app(tmp_path).openapi(), indent=2, sort_keys=True) + "\n"
    assert live == SNAPSHOT_PATH.read_text(encoding="utf-8")
