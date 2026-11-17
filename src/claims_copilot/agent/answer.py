"""The typed answer: statuses, reasons, the JSON schema the model must follow, and parsing.

The model's output is untrusted. `parse_draft` only checks shape and enum membership; whether the
citations are real and the content is allowed is decided by `validator.py`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

MAX_STATEMENTS = 12
MAX_STATEMENT_CHARS = 600
MAX_CITATIONS = 8
MAX_ID_CHARS = 120
MAX_QUOTES = 6
MAX_QUOTE_CHARS = 500
MAX_SEARCHED = 10
MAX_SEARCHED_CHARS = 200
MAX_SEARCHED_INPUT = 50


class Status(StrEnum):
    ANSWERED = "ANSWERED"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    INVALID_OUTPUT = "INVALID_OUTPUT"


class Reason(StrEnum):
    SUPPORTED = "SUPPORTED"
    SOURCES_DISAGREE = "SOURCES_DISAGREE"
    NO_RELEVANT_SOURCE = "NO_RELEVANT_SOURCE"
    TOOL_ERROR = "TOOL_ERROR"
    STEP_LIMIT = "STEP_LIMIT"
    BUDGET_LIMIT = "BUDGET_LIMIT"
    REQUEST_BLOCKED = "REQUEST_BLOCKED"
    SCHEMA_VIOLATION = "SCHEMA_VIOLATION"
    UNRESOLVED_CITATION = "UNRESOLVED_CITATION"
    VERDICT_LANGUAGE = "VERDICT_LANGUAGE"
    QUOTE_NOT_FOUND = "QUOTE_NOT_FOUND"
    PROVIDER_ERROR = "PROVIDER_ERROR"


# What the model may say. INVALID_OUTPUT and the limit reasons are assigned by the runtime only.
MODEL_STATUSES = (
    Status.ANSWERED,
    Status.CONFLICTING_EVIDENCE,
    Status.INSUFFICIENT_EVIDENCE,
    Status.OUT_OF_SCOPE,
)
MODEL_REASONS = (
    Reason.SUPPORTED,
    Reason.SOURCES_DISAGREE,
    Reason.NO_RELEVANT_SOURCE,
    Reason.TOOL_ERROR,
    Reason.REQUEST_BLOCKED,
)

# Which reasons are consistent with which status (checked for every answer, model or runtime).
ALLOWED_REASONS: dict[Status, frozenset[Reason]] = {
    Status.ANSWERED: frozenset({Reason.SUPPORTED}),
    Status.CONFLICTING_EVIDENCE: frozenset({Reason.SOURCES_DISAGREE}),
    Status.INSUFFICIENT_EVIDENCE: frozenset(
        {Reason.NO_RELEVANT_SOURCE, Reason.TOOL_ERROR, Reason.STEP_LIMIT, Reason.BUDGET_LIMIT}
    ),
    Status.OUT_OF_SCOPE: frozenset({Reason.REQUEST_BLOCKED}),
    Status.INVALID_OUTPUT: frozenset(
        {
            Reason.SCHEMA_VIOLATION,
            Reason.UNRESOLVED_CITATION,
            Reason.VERDICT_LANGUAGE,
            Reason.QUOTE_NOT_FOUND,
            Reason.PROVIDER_ERROR,
        }
    ),
}


def answer_schema() -> dict[str, Any]:
    """JSON schema sent to the providers. Every property is required, as strict modes need."""
    return {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": [s.value for s in MODEL_STATUSES]},
            "reason": {"type": "string", "enum": [r.value for r in MODEL_REASONS]},
            "summary": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "citations": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["text", "citations"],
                    "additionalProperties": False,
                },
            },
            "policy_quotes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "chunk_id": {"type": "string"},
                        "quote": {"type": "string"},
                    },
                    "required": ["chunk_id", "quote"],
                    "additionalProperties": False,
                },
            },
            "searched": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["status", "reason", "summary", "policy_quotes", "searched"],
        "additionalProperties": False,
    }


@dataclass(frozen=True)
class Statement:
    text: str
    citations: tuple[str, ...]


@dataclass(frozen=True)
class PolicyQuote:
    chunk_id: str
    quote: str


@dataclass(frozen=True)
class Draft:
    """A shape-valid model answer. Not yet trusted."""

    status: Status
    reason: Reason
    statements: tuple[Statement, ...]
    quotes: tuple[PolicyQuote, ...]
    searched: tuple[str, ...]


@dataclass(frozen=True)
class FinalAnswer:
    """What the system will show. `shown_as_answer` is False only for INVALID_OUTPUT."""

    status: Status
    reason: Reason
    statements: tuple[Statement, ...] = ()
    policy_quotes: tuple[PolicyQuote, ...] = ()
    searched: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()

    @property
    def shown_as_answer(self) -> bool:
        return self.status is not Status.INVALID_OUTPUT

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "reason": self.reason.value,
            "summary": [{"text": s.text, "citations": list(s.citations)} for s in self.statements],
            "policy_quotes": [
                {"chunk_id": q.chunk_id, "quote": q.quote} for q in self.policy_quotes
            ],
            "searched": list(self.searched),
            "issues": list(self.issues),
            "shown_as_answer": self.shown_as_answer,
        }


# Stable, model-text-free classes for a SCHEMA_VIOLATION, recorded in the audit log so a
# withheld answer is diagnosable afterwards without persisting raw model text (KF-074).
# When you add a SCHEMA_VIOLATION producer, map it here; the tests build every producer
# through the real code path, so a producer whose text drifts fails a test.
def schema_issue_class(answer: FinalAnswer) -> str | None:
    """The failure class of a SCHEMA_VIOLATION, or None for any other reason.

    Classes: `parse` (the envelope did not parse or match the schema), `status_reason_mismatch`,
    `status_with_evidence` (a refusal-class status carried statements or quotes), the loop's own
    three (`output_limit`, `refusal`, `tool_when_disabled`), and `unknown` (no issue recorded).
    """
    if answer.reason is not Reason.SCHEMA_VIOLATION:
        return None
    first = answer.issues[0] if answer.issues else ""
    if first == "the provider stopped at the output limit":  # loop._final
        return "output_limit"
    if first == "the provider refused to answer":  # loop._final
        return "refusal"
    if first == "the model called a tool when tools were disabled":  # loop._run
        return "tool_when_disabled"
    if " does not fit " in first:  # validator.validate_draft: reason vs status
        return "status_reason_mismatch"
    if " must have no " in first:  # validator.validate_draft: refusal-class status with evidence
        return "status_with_evidence"
    if first:
        return "parse"  # validate_text's only other SCHEMA_VIOLATION source is the DraftError
    return "unknown"


class DraftError(ValueError):
    """The model output does not match the schema. The message never repeats the output."""


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise DraftError(message)


def _text_list(value: Any, name: str, max_items: int, max_chars: int) -> tuple[str, ...]:
    _expect(isinstance(value, list), f"{name} must be a list")
    _expect(len(value) <= max_items, f"{name} has more than {max_items} items")
    for item in value:
        _expect(isinstance(item, str), f"{name} items must be strings")
        _expect(len(item) <= max_chars, f"{name} item is longer than {max_chars} characters")
    return tuple(value)


def parse_draft(text: str) -> Draft:
    """Parse model text into a Draft. Strict: no extra keys, enum members only, size limits."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, RecursionError):
        raise DraftError("output is not valid JSON") from None
    _expect(isinstance(data, dict), "output must be a JSON object")
    expected = {"status", "reason", "summary", "policy_quotes", "searched"}
    _expect(set(data) == expected, "output keys do not match the schema")

    status_raw, reason_raw = data["status"], data["reason"]
    _expect(isinstance(status_raw, str) and isinstance(reason_raw, str), "status/reason not text")
    try:
        status = Status(status_raw)
        reason = Reason(reason_raw)
    except ValueError:
        raise DraftError("status or reason is not an allowed value") from None
    _expect(status in MODEL_STATUSES, "status is not one the model may choose")
    _expect(reason in MODEL_REASONS, "reason is not one the model may choose")

    summary = data["summary"]
    _expect(isinstance(summary, list), "summary must be a list")
    _expect(len(summary) <= MAX_STATEMENTS, f"summary has more than {MAX_STATEMENTS} statements")
    statements: list[Statement] = []
    for item in summary:
        _expect(isinstance(item, dict) and set(item) == {"text", "citations"}, "bad summary item")
        _expect(
            isinstance(item["text"], str) and len(item["text"]) <= MAX_STATEMENT_CHARS,
            "statement text is not a short string",
        )
        citations = _text_list(item["citations"], "citations", MAX_CITATIONS, MAX_ID_CHARS)
        statements.append(Statement(item["text"], citations))

    raw_quotes = data["policy_quotes"]
    _expect(isinstance(raw_quotes, list), "policy_quotes must be a list")
    _expect(len(raw_quotes) <= MAX_QUOTES, f"more than {MAX_QUOTES} policy quotes")
    quotes: list[PolicyQuote] = []
    for item in raw_quotes:
        _expect(isinstance(item, dict) and set(item) == {"chunk_id", "quote"}, "bad policy quote")
        _expect(
            isinstance(item["chunk_id"], str) and len(item["chunk_id"]) <= MAX_ID_CHARS,
            "bad quote chunk_id",
        )
        _expect(
            isinstance(item["quote"], str) and 0 < len(item["quote"]) <= MAX_QUOTE_CHARS,
            "quote is not a short non-empty string",
        )
        quotes.append(PolicyQuote(item["chunk_id"], item["quote"]))

    # The model must send `searched` (the schema requires it) but the runtime never shows it: the
    # loop replaces it with its own tool log. So shape is checked and size is only bounded.
    raw_searched = data["searched"]
    _expect(isinstance(raw_searched, list), "searched must be a list")
    _expect(len(raw_searched) <= MAX_SEARCHED_INPUT, "searched has too many items")
    _expect(all(isinstance(item, str) for item in raw_searched), "searched items must be strings")
    searched = tuple(item[:MAX_SEARCHED_CHARS] for item in raw_searched[:MAX_SEARCHED])
    return Draft(status, reason, tuple(statements), tuple(quotes), searched)
