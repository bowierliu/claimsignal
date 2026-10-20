"""Provider-neutral types for the agent loop.

Adapters translate these to and from each provider's wire format. Nothing here knows about a
specific provider, and nothing here spends money: the loop wraps every `Provider.complete` call in
`CostGuard`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from claims_copilot.budget import Usage

StopKind = Literal["end", "tool_calls", "length", "refusal", "other"]


class ProviderError(RuntimeError):
    """A provider call failed. Messages carry a status code at most, never a response body."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ModelTurn:
    """One model response. `raw` is provider-specific replay data for the next request."""

    text: str
    tool_calls: tuple[ToolCall, ...]
    stop: StopKind
    usage: Usage
    raw: Any = None


@dataclass(frozen=True)
class ToolOutput:
    call_id: str
    name: str
    content: str
    is_error: bool


@dataclass(frozen=True)
class UserMessage:
    text: str


@dataclass(frozen=True)
class AssistantMessage:
    turn: ModelTurn


@dataclass(frozen=True)
class ToolMessage:
    outputs: tuple[ToolOutput, ...]


Message = UserMessage | AssistantMessage | ToolMessage


class Provider(Protocol):
    """One swappable model backend. Adapters do no budgeting; the loop uses `CostGuard`."""

    name: str
    model_key: str  # "provider/model", the key in budget/prices.toml

    def complete(
        self,
        *,
        system: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        schema: dict[str, Any],
        max_output_tokens: int,
        allow_tools: bool,
    ) -> ModelTurn: ...
