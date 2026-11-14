"""Result types shared by every tool.

A tool returns findings with references, never a verdict. A finding is named after what the data
shows. An empty result still says what was examined, and `limits` says what could not be checked.
All records are frozen and hold plain strings and numbers, so they serialize cleanly in Phase 4.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Pairs = tuple[tuple[str, str], ...]
Status = Literal["found", "nothing_found", "not_scored"]


@dataclass(frozen=True)
class Ref:
    """A pointer to one row the finding rests on. `kind` is claim, line, member, provider, or
    rule; `id` is the row's key in `payer.sqlite` (for a rule, the rule table and its key)."""

    kind: str
    id: str


@dataclass(frozen=True)
class Finding:
    check: str  # stable machine name, for example "bundle_pair_without_exception"
    summary: str  # one sentence stating what the data shows
    refs: tuple[Ref, ...]
    detail: Pairs = ()

    def ids(self, kind: str) -> tuple[str, ...]:
        return tuple(r.id for r in self.refs if r.kind == kind)


@dataclass(frozen=True)
class ToolResult:
    tool: str
    subject: str  # the id the tool was asked about
    examined: str  # what was looked at, in words, including counts
    findings: tuple[Finding, ...]
    observations: tuple[Finding, ...] = ()  # worth showing, but the rule did not trip
    metrics: Pairs = ()  # numbers behind the result, as text
    parameters: Pairs = ()  # rule or statistic settings used
    limits: tuple[str, ...] = ()  # what this run could not check
    status_reason: str | None = None  # set only when the tool skipped evaluation

    def has_findings(self) -> bool:
        return bool(self.findings)

    def status(self) -> Status:
        """Derived, so it cannot disagree with the findings or the skip reason."""
        if self.status_reason is not None:
            return "not_scored"
        return "found" if self.findings else "nothing_found"
