"""Provider adapters over httpx.MockTransport: wire format, parsing, retries, safe errors."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from agent_fixtures import answer_json
from claims_copilot.agent.answer import answer_schema
from claims_copilot.agent.providers import AnthropicProvider, OpenAIProvider
from claims_copilot.agent.types import (
    AssistantMessage,
    ModelTurn,
    ProviderError,
    ToolCall,
    ToolMessage,
    ToolOutput,
    ToolSpec,
    UserMessage,
)
from claims_copilot.budget import Usage

KEY = "fake-key-for-tests"
TOOLS = [
    ToolSpec(
        "get_claim",
        "Fetch a claim.",
        {
            "type": "object",
            "properties": {"claim_id": {"type": "string"}},
            "required": ["claim_id"],
            "additionalProperties": False,
        },
    )
]


class Recorder:
    def __init__(self, *responses: httpx.Response) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)

    def body(self, i: int = 0) -> dict[str, Any]:
        return json.loads(self.requests[i].content)  # type: ignore[no-any-return]


def json_response(payload: dict[str, Any], status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload)


def openai(rec: Recorder, sleeps: list[float] | None = None) -> OpenAIProvider:
    return OpenAIProvider(
        KEY,
        "gpt-test",
        transport=rec.transport,
        sleep=(sleeps if sleeps is not None else []).append,
        base_url="https://openai.invalid/v1",
    )


def anthropic(rec: Recorder, sleeps: list[float] | None = None) -> AnthropicProvider:
    return AnthropicProvider(
        KEY,
        "claude-test",
        transport=rec.transport,
        sleep=(sleeps if sleeps is not None else []).append,
        base_url="https://anthropic.invalid/v1",
    )


def history(raw_assistant: Any) -> list[Any]:
    turn = ModelTurn("", (ToolCall("c1", "get_claim", {"claim_id": "C1"}),), "tool_calls",
                     Usage(1, 1), raw=raw_assistant)  # fmt: skip
    return [
        UserMessage("question"),
        AssistantMessage(turn),
        ToolMessage((ToolOutput("c1", "get_claim", '{"ok":true}', False),)),
    ]


def complete(provider: Any, messages: list[Any], *, allow_tools: bool = True) -> ModelTurn:
    turn: ModelTurn = provider.complete(
        system="SYS",
        messages=messages,
        tools=TOOLS,
        schema=answer_schema(),
        max_output_tokens=777,
        allow_tools=allow_tools,
    )
    return turn


# ------------------------------------------------------------------ OpenAI

OPENAI_CALL = {
    "status": "completed",
    "output": [
        {"type": "reasoning", "id": "rs_1", "summary": []},
        {
            "type": "function_call",
            "call_id": "call_9",
            "name": "get_claim",
            "arguments": '{"claim_id": "C0000001"}',
        },
    ],
    "usage": {"input_tokens": 120, "output_tokens": 30},
}
OPENAI_FINAL = {
    "status": "completed",
    "output": [
        {
            "type": "message",
            "content": [{"type": "output_text", "text": answer_json()}],
        }
    ],
    "usage": {"input_tokens": 200, "output_tokens": 50},
}


def test_openai_request_uses_the_documented_responses_fields() -> None:
    rec = Recorder(json_response(OPENAI_CALL))
    complete(openai(rec), [UserMessage("hello")])
    request, body = rec.requests[0], rec.body()
    assert request.url.path == "/v1/responses" and request.method == "POST"
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert body["model"] == "gpt-test" and body["instructions"] == "SYS"
    assert body["input"] == [{"role": "user", "content": "hello"}]
    assert body["max_output_tokens"] == 777 and body["tool_choice"] == "auto"
    assert body["tools"][0] == {
        "type": "function",
        "name": "get_claim",
        "description": "Fetch a claim.",
        "parameters": TOOLS[0].parameters,
        "strict": False,
    }
    fmt = body["text"]["format"]
    assert fmt["type"] == "json_schema" and fmt["strict"] is True and fmt["schema"]


def test_openai_disables_tools_on_the_last_turn() -> None:
    rec = Recorder(json_response(OPENAI_FINAL))
    complete(openai(rec), [UserMessage("hello")], allow_tools=False)
    assert rec.body()["tool_choice"] == "none"


def test_openai_replays_assistant_output_and_sends_tool_results() -> None:
    rec = Recorder(json_response(OPENAI_FINAL))
    raw = OPENAI_CALL["output"]
    complete(openai(rec), history(raw))
    items = rec.body()["input"]
    assert items[0] == {"role": "user", "content": "question"}
    assert items[1:3] == raw
    assert items[3] == {"type": "function_call_output", "call_id": "c1", "output": '{"ok":true}'}


def test_openai_parses_a_tool_call_and_usage() -> None:
    turn = complete(openai(Recorder(json_response(OPENAI_CALL))), [UserMessage("q")])
    assert turn.stop == "tool_calls" and turn.usage == Usage(120, 30)
    assert turn.tool_calls == (ToolCall("call_9", "get_claim", {"claim_id": "C0000001"}),)


def test_openai_parses_a_final_answer_refusal_and_incomplete() -> None:
    final = complete(openai(Recorder(json_response(OPENAI_FINAL))), [UserMessage("q")])
    assert final.stop == "end" and json.loads(final.text)["status"] == "ANSWERED"
    refusal = {
        **OPENAI_FINAL,
        "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "no"}]}],
    }
    assert complete(openai(Recorder(json_response(refusal))), [UserMessage("q")]).stop == "refusal"
    incomplete = {**OPENAI_FINAL, "status": "incomplete"}
    assert (
        complete(openai(Recorder(json_response(incomplete))), [UserMessage("q")]).stop == "length"
    )


def test_openai_unparseable_tool_arguments_become_a_rejectable_call() -> None:
    bad = {
        **OPENAI_CALL,
        "output": [
            {"type": "function_call", "call_id": "c", "name": "get_claim", "arguments": "{"}
        ],
    }
    turn = complete(openai(Recorder(json_response(bad))), [UserMessage("q")])
    assert turn.tool_calls[0].arguments == {"_unparseable": "true"}


def test_openai_retries_transient_errors_with_backoff() -> None:
    rec = Recorder(httpx.Response(500), httpx.Response(429), json_response(OPENAI_FINAL))
    sleeps: list[float] = []
    turn = complete(openai(rec, sleeps), [UserMessage("q")])
    assert turn.stop == "end" and len(rec.requests) == 3 and sleeps == [2.0, 4.0]


def test_openai_errors_never_include_response_bodies_or_keys() -> None:
    leak = httpx.Response(401, text=f"Incorrect API key provided: {KEY}")
    with pytest.raises(ProviderError) as err:
        complete(openai(Recorder(leak)), [UserMessage("q")])
    assert str(err.value) == "OpenAI responses request failed: HTTP 401"
    assert KEY not in str(err.value)


def test_openai_gives_up_after_the_attempt_limit() -> None:
    rec = Recorder(httpx.Response(503))
    with pytest.raises(ProviderError, match="gave up after 3 attempts"):
        complete(openai(rec), [UserMessage("q")])
    assert len(rec.requests) == 3


def test_openai_unexpected_shapes_are_provider_errors() -> None:
    payloads: list[dict[str, Any]] = [{"status": "completed"}, {"output": [], "usage": {}}]
    for payload in payloads:
        with pytest.raises(ProviderError, match="unexpected OpenAI response shape"):
            complete(openai(Recorder(json_response(payload))), [UserMessage("q")])


def test_an_empty_key_is_refused() -> None:
    with pytest.raises(ProviderError):
        OpenAIProvider("", "m")
    with pytest.raises(ProviderError):
        AnthropicProvider("", "m")


# ------------------------------------------------------------------ Anthropic

ANTHROPIC_CALL = {
    "stop_reason": "tool_use",
    "content": [
        {"type": "text", "text": "Checking.", "citations": None},
        {"type": "tool_use", "id": "toolu_1", "name": "get_claim", "input": {"claim_id": "C1"}},
    ],
    "usage": {"input_tokens": 100, "output_tokens": 20},
}
ANTHROPIC_FINAL = {
    "stop_reason": "end_turn",
    "content": [{"type": "text", "text": answer_json()}],
    "usage": {
        "input_tokens": 300,
        "output_tokens": 40,
        "cache_creation_input_tokens": 5,
        "cache_read_input_tokens": 7,
    },
}


def test_anthropic_request_uses_the_documented_messages_fields() -> None:
    rec = Recorder(json_response(ANTHROPIC_FINAL))
    complete(anthropic(rec), [UserMessage("hello")])
    request, body = rec.requests[0], rec.body()
    assert request.url.path == "/v1/messages" and request.method == "POST"
    assert request.headers["x-api-key"] == KEY
    assert request.headers["anthropic-version"] == "2023-06-01"
    assert body["model"] == "claude-test" and body["system"] == "SYS"
    assert body["max_tokens"] == 777 and body["tool_choice"] == {"type": "auto"}
    assert body["messages"] == [{"role": "user", "content": "hello"}]
    assert body["tools"] == [
        {
            "name": "get_claim",
            "description": "Fetch a claim.",
            "input_schema": TOOLS[0].parameters,
        }
    ]
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["output_config"]["format"]["schema"]["additionalProperties"] is False


def test_anthropic_disables_tools_on_the_last_turn() -> None:
    rec = Recorder(json_response(ANTHROPIC_FINAL))
    complete(anthropic(rec), [UserMessage("hello")], allow_tools=False)
    assert rec.body()["tool_choice"] == {"type": "none"}


def test_anthropic_parses_tool_use_and_keeps_replay_blocks_clean() -> None:
    turn = complete(anthropic(Recorder(json_response(ANTHROPIC_CALL))), [UserMessage("q")])
    assert turn.stop == "tool_calls" and turn.usage == Usage(100, 20)
    assert turn.tool_calls == (ToolCall("toolu_1", "get_claim", {"claim_id": "C1"}),)
    assert turn.raw[0] == {"type": "text", "text": "Checking."}  # output-only fields dropped
    assert turn.raw[1]["type"] == "tool_use"


def test_anthropic_sends_tool_results_in_a_user_message() -> None:
    rec = Recorder(json_response(ANTHROPIC_FINAL))
    turn = complete(anthropic(Recorder(json_response(ANTHROPIC_CALL))), [UserMessage("q")])
    messages = [*history(turn.raw)]
    messages[2] = ToolMessage(
        (
            ToolOutput("toolu_1", "get_claim", '{"ok":true}', False),
            ToolOutput("toolu_2", "get_claim", '{"error":"x"}', True),
        )
    )
    complete(anthropic(rec), messages)
    sent = rec.body()["messages"]
    assert sent[1] == {"role": "assistant", "content": turn.raw}
    assert sent[2] == {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_1",
                "content": '{"ok":true}',
                "is_error": False,
            },
            {
                "type": "tool_result",
                "tool_use_id": "toolu_2",
                "content": '{"error":"x"}',
                "is_error": True,
            },
        ],
    }


def test_anthropic_final_answer_usage_counts_cache_tokens_conservatively() -> None:
    turn = complete(anthropic(Recorder(json_response(ANTHROPIC_FINAL))), [UserMessage("q")])
    assert turn.stop == "end" and turn.usage == Usage(312, 40)
    assert json.loads(turn.text)["status"] == "ANSWERED"


def test_anthropic_stop_reasons_map_to_neutral_kinds() -> None:
    for reason, expected in (("max_tokens", "length"), ("refusal", "refusal"), ("odd", "other")):
        payload = {**ANTHROPIC_FINAL, "stop_reason": reason}
        turn = complete(anthropic(Recorder(json_response(payload))), [UserMessage("q")])
        assert turn.stop == expected


def test_anthropic_retries_and_hides_error_bodies() -> None:
    rec = Recorder(httpx.Response(529), json_response(ANTHROPIC_FINAL))
    sleeps: list[float] = []
    assert complete(anthropic(rec, sleeps), [UserMessage("q")]).stop == "end"
    assert sleeps == [2.0]
    leak = httpx.Response(401, text=f"invalid x-api-key: {KEY}")
    with pytest.raises(ProviderError) as err:
        complete(anthropic(Recorder(leak)), [UserMessage("q")])
    assert str(err.value) == "Anthropic messages request failed: HTTP 401"


def test_anthropic_unexpected_shapes_are_provider_errors() -> None:
    with pytest.raises(ProviderError, match="unexpected Anthropic response shape"):
        complete(anthropic(Recorder(json_response({"content": []}))), [UserMessage("q")])
