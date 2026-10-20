"""Deterministic validation of model output (see ANSWER_BOUNDARY.md).

Plain code, no model. A draft that fails any rule is returned as INVALID_OUTPUT with the first
failing reason and every issue found; it is not shown as an answer. Rules 2 and 4 prove that a
citation exists and a quote is verbatim, not that the cited evidence supports the sentence: that
needs a judge and hand labels (Phase 7).
"""

from __future__ import annotations

import re

from claims_copilot.agent.answer import (
    ALLOWED_REASONS,
    Draft,
    DraftError,
    FinalAnswer,
    Reason,
    Status,
    parse_draft,
)
from claims_copilot.agent.evidence import EvidenceRegistry

# Words and phrases that would turn a description of data into a conclusion.
VERDICT_PATTERN = re.compile(
    r"\b(fraud\w*|abus\w*|improper\w*|den(y|ied|ial|ies|ying)|overpa\w+|"
    r"medically (un)?necessary|medical necessity|recoup\w*|guilty|scheme|intent\w*|illegal|"
    r"wrongdoing|suspicio\w+|recommend\w*|"
    r"should (be )?(paid|approved|rejected|pended|referred|denied|recouped))\b",
    re.IGNORECASE,
)
_SPACE = re.compile(r"\s+")


def _clip(text: str, limit: int = 60) -> str:
    return text if len(text) <= limit else text[:limit] + "..."


def _norm(text: str) -> str:
    return _SPACE.sub(" ", text).strip()


def validate_text(text: str, registry: EvidenceRegistry) -> FinalAnswer:
    try:
        draft = parse_draft(text)
    except DraftError as exc:
        return invalid(Reason.SCHEMA_VIOLATION, str(exc))
    return validate_draft(draft, registry)


def invalid(reason: Reason, *issues: str) -> FinalAnswer:
    return FinalAnswer(Status.INVALID_OUTPUT, reason, issues=tuple(issues))


def validate_draft(draft: Draft, registry: EvidenceRegistry) -> FinalAnswer:
    failures: list[tuple[Reason, str]] = []

    # Status and reason must agree (the model cannot pair ANSWERED with BUDGET_LIMIT, say).
    if draft.reason not in ALLOWED_REASONS[draft.status]:
        failures.append(
            (Reason.SCHEMA_VIOLATION, f"reason {draft.reason.value} does not fit {draft.status}")
        )

    cited = [c for s in draft.statements for c in s.citations]
    # Rule 2: every citation resolves to something this run actually retrieved.
    for citation in dict.fromkeys(cited):
        if not registry.has(citation):
            failures.append((Reason.UNRESOLVED_CITATION, f"unknown citation: {_clip(citation)}"))

    # Rules 3 and 6: citation counts per status, and no uncited statement.
    if draft.status in (Status.ANSWERED, Status.CONFLICTING_EVIDENCE):
        if not draft.statements:
            failures.append((Reason.UNRESOLVED_CITATION, f"{draft.status} needs a summary"))
        for statement in draft.statements:
            if not statement.citations:
                failures.append(
                    (Reason.UNRESOLVED_CITATION, f"uncited statement: {_clip(statement.text)}")
                )
        unique = list(dict.fromkeys(c for c in cited if registry.has(c)))
        if draft.status is Status.ANSWERED and len(unique) < 1:
            failures.append((Reason.UNRESOLVED_CITATION, "ANSWERED needs at least 1 citation"))
        if draft.status is Status.CONFLICTING_EVIDENCE:
            sources = {registry.source_key(c) for c in unique}
            if len(unique) < 2 or len(sources) < 2:
                failures.append(
                    (
                        Reason.UNRESOLVED_CITATION,
                        "CONFLICTING_EVIDENCE needs 2 citations from 2 distinct sources",
                    )
                )
    else:
        # Rule 7: refusals and "not enough evidence" carry no evidence framed as a conclusion.
        if draft.statements:
            failures.append((Reason.SCHEMA_VIOLATION, f"{draft.status} must have no summary"))
        if draft.quotes:
            failures.append((Reason.SCHEMA_VIOLATION, f"{draft.status} must have no quotes"))
        if draft.status is Status.INSUFFICIENT_EVIDENCE and not draft.searched:
            failures.append(
                (Reason.SCHEMA_VIOLATION, "INSUFFICIENT_EVIDENCE must say what was searched")
            )

    # Rule 4: quotes are verbatim from a retrieved chunk.
    for quote in draft.quotes:
        chunk = registry.chunk_text(quote.chunk_id)
        if chunk is None:
            failures.append(
                (Reason.UNRESOLVED_CITATION, f"quote cites unknown chunk: {_clip(quote.chunk_id)}")
            )
        elif _norm(quote.quote) not in _norm(chunk):
            failures.append((Reason.QUOTE_NOT_FOUND, f"quote not found in {_clip(quote.chunk_id)}"))

    # Rule 5: no verdict language in what the model wrote (quotes are the source's own words).
    written = [s.text for s in draft.statements] + list(draft.searched)
    for text in written:
        match = VERDICT_PATTERN.search(text)
        if match:
            failures.append((Reason.VERDICT_LANGUAGE, f"verdict language: {match.group(0)!r}"))

    if failures:
        return invalid(failures[0][0], *[message for _, message in failures])
    return FinalAnswer(draft.status, draft.reason, draft.statements, draft.quotes, draft.searched)
