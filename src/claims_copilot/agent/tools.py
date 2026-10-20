"""Runs the allow-listed read-only API operations on behalf of the model.

The allow-list is the API's own `GET /v1/tools` manifest, so the model can call exactly those
operations and nothing else. Arguments are checked for shape here (names, scalar types), and for
content by the API's validators; error bodies from the API name the parameter but never echo the
value, and they are returned to the model as data.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from claims_copilot.agent.evidence import EvidenceRegistry, ResultTooLargeError, dumps, trim
from claims_copilot.agent.types import ToolCall, ToolOutput, ToolSpec

MAX_RESULT_CHARS = 24_000
MAX_ERROR_CHARS = 300
BASE_URL = "http://api.local"
# Values that become part of a URL path. A "/" would otherwise be decoded by the server and could
# reach a different route than the tool the model named.
PATH_VALUE = re.compile(r"[A-Za-z0-9._:~-]{1,64}")


def in_process_client(app: FastAPI) -> httpx.Client:
    """An HTTP client bound to the app in this process: same contract, no server, no network."""
    return TestClient(app, base_url=BASE_URL, raise_server_exceptions=False)


class ToolRunner:
    def __init__(self, client: httpx.Client, *, max_result_chars: int = MAX_RESULT_CHARS) -> None:
        self._client = client
        self._max_chars = max_result_chars
        response = client.get("/v1/tools")
        response.raise_for_status()
        self._defs: dict[str, dict[str, Any]] = {t["name"]: t for t in response.json()["tools"]}
        if not self._defs:
            raise ValueError("the API lists no tools")

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(name, str(d["description"]), dict(d["parameters"]))
            for name, d in sorted(self._defs.items())
        ]

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self._defs)

    def execute(self, call: ToolCall, registry: EvidenceRegistry) -> ToolOutput:
        """Run one call. Failures become error outputs for the model; they never raise."""
        definition = self._defs.get(call.name)
        if definition is None:
            return self._error(call, "unknown tool; use only the listed tools")
        problem = self._check_arguments(definition, call.arguments)
        if problem:
            return self._error(call, problem)
        path, query = self._build_request(definition, call.arguments)
        try:
            response = self._client.get(path, params=query)
        except httpx.HTTPError as exc:
            return self._error(call, f"request failed: {type(exc).__name__}")
        if response.status_code != 200:
            return self._error(call, self._api_error(response))
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("not an object")
            trimmed = trim(payload, self._max_chars)
        except ResultTooLargeError:
            return self._error(call, "result too large to show; narrow the request")
        except ValueError:
            return self._error(call, "the API returned an unreadable result")
        registry.register_result(trimmed)
        return ToolOutput(call.call_id, call.name, dumps(trimmed), False)

    @staticmethod
    def _check_arguments(definition: Mapping[str, Any], arguments: Mapping[str, Any]) -> str | None:
        params = definition["parameters"]
        known: dict[str, Any] = params.get("properties", {})
        extra = sorted(set(arguments) - set(known))
        if extra:
            return f"unknown argument(s): {', '.join(_safe_name(n) for n in extra)}"
        missing = sorted(set(params.get("required", [])) - set(arguments))
        if missing:
            return f"missing required argument(s): {', '.join(missing)}"
        path = str(definition["path"])
        for name, value in arguments.items():
            if isinstance(value, bool) or not isinstance(value, str | int):
                return f"argument {name} must be a string or an integer"
            if "{" + name + "}" in path and not PATH_VALUE.fullmatch(str(value)):
                return f"argument {name} has characters that are not allowed in an identifier"
        return None

    @staticmethod
    def _build_request(
        definition: Mapping[str, Any], arguments: Mapping[str, Any]
    ) -> tuple[str, dict[str, str]]:
        path = str(definition["path"])
        query: dict[str, str] = {}
        for name, value in arguments.items():
            token = "{" + name + "}"
            if token in path:
                path = path.replace(token, quote(str(value), safe=""))
            else:
                query[name] = str(value)
        return path, query

    @staticmethod
    def _api_error(response: httpx.Response) -> str:
        """Problem bodies name the parameter but never echo its value; keep only that."""
        try:
            body = response.json()
            title = str(body.get("title", ""))
            detail = str(body.get("detail", ""))
        except (ValueError, AttributeError):
            title = detail = ""
        message = f"HTTP {response.status_code}: {title} {detail}".strip()
        return message[:MAX_ERROR_CHARS]

    @staticmethod
    def _error(call: ToolCall, message: str) -> ToolOutput:
        return ToolOutput(call.call_id, call.name, json.dumps({"error": message}), True)


def _safe_name(name: str) -> str:
    return name[:40]
