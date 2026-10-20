"""OpenAI adapter over the Responses API (POST /v1/responses).

Request and response field names were taken from the fetched OpenAI documentation recorded in
SOURCES/manifest.jsonl (`openai-api-tool-calling`, `openai-api-structured-outputs`,
`openai-api-responses-create`), not from memory. The adapter does no budgeting; the loop wraps
every call in CostGuard.
"""

from __future__ import annotations

import json
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

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIProvider:
    name = "openai"

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
            raise ProviderError("OPENAI_API_KEY is not set")
        self.model = model
        self.model_key = f"openai/{model}"
        self._url = f"{base_url}/responses"
        self._max_attempts = max_attempts
        self._backoff_s = backoff_s
        self._sleep = sleep
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
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
            "instructions": system,
            "input": self._input_items(messages),
            "tools": [
                {
                    "type": "function",
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                    "strict": False,
                }
                for t in tools
            ],
            "tool_choice": "auto" if allow_tools else "none",
            "max_output_tokens": max_output_tokens,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "evidence_answer",
                    "schema": schema,
                    "strict": True,
                }
            },
        }
        payload = post_json(
            self._client,
            self._url,
            body,
            what="OpenAI responses request",
            max_attempts=self._max_attempts,
            backoff_s=self._backoff_s,
            sleep=self._sleep,
        )
        return self._parse(payload)

    @staticmethod
    def _input_items(messages: Sequence[Message]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for message in messages:
            if isinstance(message, UserMessage):
                items.append({"role": "user", "content": message.text})
            elif isinstance(message, AssistantMessage):
                items.extend(message.turn.raw or [])
            elif isinstance(message, ToolMessage):
                items.extend(
                    {"type": "function_call_output", "call_id": o.call_id, "output": o.content}
                    for o in message.outputs
                )
        return items

    @staticmethod
    def _parse(payload: dict[str, Any]) -> ModelTurn:
        try:
            output = payload["output"]
            usage = payload["usage"]
            tokens = Usage(int(usage["input_tokens"]), int(usage["output_tokens"]))
            texts: list[str] = []
            calls: list[ToolCall] = []
            refused = False
            for item in output:
                kind = item.get("type")
                if kind == "function_call":
                    try:
                        arguments = json.loads(item["arguments"])
                    except (json.JSONDecodeError, TypeError):
                        arguments = None
                    if not isinstance(arguments, dict):
                        arguments = {"_unparseable": "true"}
                    calls.append(ToolCall(str(item["call_id"]), str(item["name"]), arguments))
                elif kind == "message":
                    for part in item.get("content", []):
                        if part.get("type") == "output_text":
                            texts.append(str(part["text"]))
                        elif part.get("type") == "refusal":
                            refused = True
            status = payload.get("status")
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ProviderError(f"unexpected OpenAI response shape: {type(exc).__name__}") from None
        stop: StopKind
        if calls:
            stop = "tool_calls"
        elif refused:
            stop = "refusal"
        elif status == "incomplete":
            stop = "length"
        elif status == "completed":
            stop = "end"
        else:
            stop = "other"
        return ModelTurn("".join(texts), tuple(calls), stop, tokens, raw=list(output))
