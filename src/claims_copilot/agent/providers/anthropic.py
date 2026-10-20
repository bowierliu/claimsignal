"""Anthropic adapter over the Messages API (POST /v1/messages).

Field names were taken from the fetched Anthropic documentation recorded in
SOURCES/manifest.jsonl (`anthropic-api-tool-use`, `anthropic-api-define-tools`,
`anthropic-api-structured-outputs`, `anthropic-api-messages-create`), not from memory. The adapter
does no budgeting; the loop wraps every call in CostGuard.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Any

import httpx

from claims_copilot.agent.providers.http import post_json
from claims_copilot.agent.types import (
    AssistantMessage,
    Message,
    ModelTurn,
    ProviderError,
    StopKind,
    ToolCall,
    ToolMessage,
    ToolSpec,
    UserMessage,
)
from claims_copilot.budget import Usage

DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
API_VERSION = "2023-06-01"  # the value shown in the fetched documentation examples

_STOP: dict[str, StopKind] = {
    "end_turn": "end",
    "tool_use": "tool_calls",
    "max_tokens": "length",
    "refusal": "refusal",
}


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        transport: httpx.BaseTransport | None = None,
        max_attempts: int = 3,
        backoff_s: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
        timeout_s: float = 90.0,
    ) -> None:
        if not api_key:
            raise ProviderError("ANTHROPIC_API_KEY is not set")
        self.model = model
        self.model_key = f"anthropic/{model}"
        self._url = f"{base_url}/messages"
        self._max_attempts = max_attempts
        self._backoff_s = backoff_s
        self._sleep = sleep
        self._client = httpx.Client(
            headers={
                "x-api-key": api_key,
                "anthropic-version": API_VERSION,
                "content-type": "application/json",
            },
            timeout=timeout_s,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def complete(
        self,
        *,
        system: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        schema: dict[str, Any],
        max_output_tokens: int,
        allow_tools: bool,
    ) -> ModelTurn:
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_output_tokens,
            "system": system,
            "messages": self._messages(messages),
            "tools": [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in tools
            ],
            "tool_choice": {"type": "auto" if allow_tools else "none"},
            "output_config": {"format": {"type": "json_schema", "schema": schema}},
        }
        payload = post_json(
            self._client,
            self._url,
            body,
            what="Anthropic messages request",
            max_attempts=self._max_attempts,
            backoff_s=self._backoff_s,
            sleep=self._sleep,
        )
        return self._parse(payload)

    @staticmethod
    def _messages(messages: Sequence[Message]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for message in messages:
            if isinstance(message, UserMessage):
                out.append({"role": "user", "content": message.text})
            elif isinstance(message, AssistantMessage):
                out.append({"role": "assistant", "content": message.turn.raw or []})
            elif isinstance(message, ToolMessage):
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": o.call_id,
                                "content": o.content,
                                "is_error": o.is_error,
                            }
                            for o in message.outputs
                        ],
                    }
                )
        return out

    @staticmethod
    def _parse(payload: dict[str, Any]) -> ModelTurn:
        try:
            usage = payload["usage"]
            tokens = Usage(
                int(usage["input_tokens"])
                + int(usage.get("cache_creation_input_tokens") or 0)
                + int(usage.get("cache_read_input_tokens") or 0),
                int(usage["output_tokens"]),
            )
            texts: list[str] = []
            calls: list[ToolCall] = []
            replay: list[dict[str, Any]] = []
            for block in payload["content"]:
                kind = block.get("type")
                if kind == "text":
                    texts.append(str(block["text"]))
                    replay.append({"type": "text", "text": str(block["text"])})
                elif kind == "tool_use":
                    arguments = block["input"]
                    if not isinstance(arguments, dict):
                        arguments = {"_unparseable": "true"}
                    calls.append(ToolCall(str(block["id"]), str(block["name"]), arguments))
                    replay.append(
                        {
                            "type": "tool_use",
                            "id": str(block["id"]),
                            "name": str(block["name"]),
                            "input": block["input"],
                        }
                    )
                else:
                    replay.append(dict(block))
            stop_reason = payload.get("stop_reason")
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ProviderError(
                f"unexpected Anthropic response shape: {type(exc).__name__}"
            ) from None
        stop: StopKind = _STOP.get(str(stop_reason), "other")
        if calls:
            stop = "tool_calls"
        return ModelTurn("".join(texts), tuple(calls), stop, tokens, raw=replay)
