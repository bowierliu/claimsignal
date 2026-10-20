"""The eval case record. Frozen, validated on construction, JSON round-trippable."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from claims_copilot.agent.answer import Status
from claims_copilot.synth.anomalies import ANOMALY_TYPES

CASE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")


class Layer(StrEnum):
    UNANSWERABLE = "unanswerable"
    TOOLS_HANDBUILT = "tools_handbuilt"
    E2E = "e2e"
    SAFETY = "safety"


class SafetyKind(StrEnum):
    OBFUSCATED_DECISION_ASK = "obfuscated_decision_ask"
    PLANTED_INJECTION = "planted_injection"
    FABRICATED_CITATION_ASK = "fabricated_citation_ask"
    VERDICT_LANGUAGE_ASK = "verdict_language_ask"


class Split(StrEnum):
    DEV = "dev"
    TEST = "test"


class CaseError(ValueError):
    """A case record is malformed."""


@dataclass(frozen=True)
class EvalCase:
    """One agent case.

    `expected_statuses` lists every status a careful reader would accept (usually one).
    `expected_anomalies` and `decoy_anomalies` use the synthetic anomaly type names and are only
    for the end-to-end layer, where the truth store says which claim holds which case. `note` is
    free text for reviewers and never sent to a model.
    """

    case_id: str
    layer: Layer
    question: str
    expected_statuses: tuple[Status, ...]
    claim_id: str | None = None
    expected_anomalies: tuple[str, ...] = ()
    decoy_anomalies: tuple[str, ...] = ()
    safety_kind: SafetyKind | None = None
    absent_terms: tuple[str, ...] = ()
    note: str = ""

    def __post_init__(self) -> None:
        if not CASE_ID.match(self.case_id):
            raise CaseError(f"bad case_id: {self.case_id!r}")
        if not self.question.strip():
            raise CaseError(f"{self.case_id}: empty question")
        if not self.expected_statuses:
            raise CaseError(f"{self.case_id}: expected_statuses is empty")
        if Status.INVALID_OUTPUT in self.expected_statuses:
            raise CaseError(f"{self.case_id}: INVALID_OUTPUT is never an expected status")
        unknown = (set(self.expected_anomalies) | set(self.decoy_anomalies)) - set(ANOMALY_TYPES)
        if unknown:
            raise CaseError(f"{self.case_id}: unknown anomaly types {sorted(unknown)}")
        if self.expected_anomalies and self.decoy_anomalies:
            raise CaseError(f"{self.case_id}: a claim is a seeded case or a decoy, not both")
        if self.layer in (Layer.E2E, Layer.TOOLS_HANDBUILT) and self.claim_id is None:
            raise CaseError(f"{self.case_id}: layer {self.layer.value} needs a claim_id")
        if self.layer is not Layer.E2E and (self.expected_anomalies or self.decoy_anomalies):
            raise CaseError(f"{self.case_id}: anomalies are only for the e2e layer")
        if (self.layer is Layer.UNANSWERABLE) != bool(self.absent_terms):
            raise CaseError(
                f"{self.case_id}: absent_terms are required for, and only for, unanswerable"
            )
        if (self.layer is Layer.SAFETY) != (self.safety_kind is not None):
            raise CaseError(f"{self.case_id}: safety_kind is required for, and only for, safety")

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "layer": self.layer.value,
            "question": self.question,
            "expected_statuses": [s.value for s in self.expected_statuses],
            "claim_id": self.claim_id,
            "expected_anomalies": list(self.expected_anomalies),
            "decoy_anomalies": list(self.decoy_anomalies),
            "safety_kind": self.safety_kind.value if self.safety_kind else None,
            "absent_terms": list(self.absent_terms),
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalCase:
        try:
            kind = data.get("safety_kind")
            return cls(
                case_id=str(data["case_id"]),
                layer=Layer(data["layer"]),
                question=str(data["question"]),
                expected_statuses=tuple(Status(s) for s in data["expected_statuses"]),
                claim_id=data.get("claim_id"),
                expected_anomalies=tuple(data.get("expected_anomalies", ())),
                decoy_anomalies=tuple(data.get("decoy_anomalies", ())),
                safety_kind=SafetyKind(kind) if kind else None,
                absent_terms=tuple(data.get("absent_terms", ())),
                note=str(data.get("note", "")),
            )
        except (KeyError, ValueError, TypeError) as exc:
            if isinstance(exc, CaseError):
                raise
            raise CaseError(f"malformed case record: {type(exc).__name__}") from exc


def check_unique(cases: list[EvalCase]) -> None:
    seen: set[str] = set()
    for case in cases:
        if case.case_id in seen:
            raise CaseError(f"duplicate case_id: {case.case_id}")
        seen.add(case.case_id)
