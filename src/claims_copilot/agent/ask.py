"""The Ask service behind the workbench's "Ask the agent" tab.

One call is one turn in a session: scope gate (on the message alone and joined to the previous
question), then a bounded investigation whose policy searches use the Ask-path search (hybrid +
rerank + the minimum-relevance rule), then a view built only from the validated `FinalAnswer` and
the runtime's own records. Model text appears only as validated statement text; every other
string in the view comes from a tool payload, a verified source, or a fixed sentence in this file.

Cost: each turn may spend at most min($0.15, session remaining - search reserve) on model turns;
the session's ledgered spend (model turns, embeddings and reranks, all under the session's
`eval_run_id`) can never pass the $0.25 ceiling. One investigation runs at a time per server.
"""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from claims_copilot.agent.answer import FinalAnswer, Reason, Status
from claims_copilot.agent.ask_search import AskPolicySearch
from claims_copilot.agent.evidence import EvidenceRegistry, ResultTooLargeError, dumps, trim
from claims_copilot.agent.loop import Investigator, Limits, RunRecord
from claims_copilot.agent.prompt import Prompt
from claims_copilot.agent.scope import BLOCK_MESSAGE, check_followup
from claims_copilot.agent.session import MAX_TURNS, PriorTurn, Session, SessionStore
from claims_copilot.agent.tools import ToolRunner
from claims_copilot.agent.types import Provider, ToolCall, ToolOutput
from claims_copilot.agent.validator import verdict_match
from claims_copilot.budget import CostGuard
from claims_copilot.obs.audit import AuditLog
from claims_copilot.obs.trace import Tracer

SESSION_CEILING_USD = Decimal("0.25")
SERVER_CEILING_USD = Decimal("2.00")
TURN_CEILING_USD = Decimal("0.15")
# Upper bound for one turn's searches (12 tool calls x about $0.0013 for a rerank and embeddings),
# held back from the model's share so a turn cannot carry the session past its ceiling.
SEARCH_RESERVE_USD = Decimal("0.03")
MAX_QUESTION_CHARS = 1000
CLAIM_ID = re.compile(r"C\d{7}")
PROVIDER_ID = re.compile(r"P\d{4}")
MEMBER_ID = re.compile(r"M\d{6}")
CHECK_PREFIXES = ("check_", "find_", "validate_")

NOT_A_DETERMINATION = "This is evidence for the investigator; it is not a determination."
SYNTHETIC_RULES = (
    "The claim checks run a synthetic ruleset invented for this demo (fake X-codes, invented "
    "bundle pairs and unit limits), not any payer's or CMS's rules."
)
INSUFFICIENT_MESSAGE = (
    "There is not enough evidence in the claims data or the cited public sources to answer this."
)
NARROWER = (
    "Try a narrower question: name the claim id, one check (for example unit limits or "
    "bundling), or the policy topic in the source's own terms."
)
CEILING_MESSAGE = "This session reached its cost ceiling. Start a new session to keep asking."
SERVER_CEILING_MESSAGE = (
    "This server reached its Ask cost ceiling. Restart the server to keep asking."
)
CEILING_TEXT = {"session_cost": CEILING_MESSAGE, "server_cost": SERVER_CEILING_MESSAGE}
ARGUMENTS_WITHHELD = "[arguments withheld: they contained decision wording]"
INVALID_MESSAGE = "The answer could not be validated, so it is not shown."
# A provider failure is not a validation failure: the banner says the service errored and the
# message says a retry may work. The adapter's error text (a status code or exception class
# name by the ProviderError contract, never a response body) goes to `detail` for Run details;
# validation-reason issue strings still never reach the view.
PROVIDER_FAILED_LABEL = "The model service failed"
PROVIDER_FAILED_MESSAGE = (
    "The model service returned an error, so there is no answer to show. "
    "Asking the question again may work."
)
EVIDENCE_QUESTIONS = (
    "What did the checks find on claim {claim}, and what could they not see?",
    "What do the policy sources say about modifiers on bundled code pairs?",
    "How does the provider on claim {claim} compare with its peers, and what are the limits?",
)
EXAMPLE_CLAIM = "C0000493"
REASON_TEXT: dict[Reason, str] = {
    Reason.NO_RELEVANT_SOURCE: "No relevant evidence was found.",
    Reason.TOOL_ERROR: "A tool returned an error, so the evidence could not be gathered.",
    Reason.STEP_LIMIT: "The run reached its turn, tool-call or time limit before it finished.",
    Reason.BUDGET_LIMIT: "The run reached its cost limit (per question or per session).",
    Reason.SCHEMA_VIOLATION: "The model's output did not match the required structure.",
    Reason.UNRESOLVED_CITATION: (
        "It cited something this run did not retrieve, or a statement had no citation."
    ),
    Reason.VERDICT_LANGUAGE: "It used decision language this product does not allow.",
    Reason.QUOTE_NOT_FOUND: "A quote was not found verbatim in the passage it cited.",
    Reason.PROVIDER_ERROR: "The model service returned an error.",
}
STATUS_LABEL = {
    Status.ANSWERED: "Answered from evidence",
    Status.CONFLICTING_EVIDENCE: "Evidence conflicts",
    Status.INSUFFICIENT_EVIDENCE: "Not enough evidence",
    Status.OUT_OF_SCOPE: "Outside what this tool does",
    Status.INVALID_OUTPUT: "Could not be validated",
}


def _claims_named(question: str) -> tuple[str, ...]:
    """Distinct claim ids named in the question, in order of first mention. The text is
    uppercased first because the claim id field already normalizes with .upper(); a lowercase
    "c0000240" in prose is the same claim."""
    return tuple(dict.fromkeys(CLAIM_ID.findall(question.upper())))


def _scope_claim(session: Session, question: str, claim_id: str | None) -> str | None:
    """Pin this turn's claim, and say so when the choice was not obvious.

    Precedence: a claim id named in the question beats the claim id field, which beats the
    session's stored claim. A question naming two different claims is ambiguous, so its text
    is ignored and the field/session value stands. Returns a note for the session line when
    an override or re-scope happened, None for the plain cases. Nothing here is silent: the
    investigator always sees which claim was investigated when it was not simply the one
    they typed.
    """
    named = _claims_named(question)
    field_id = claim_id.upper() if claim_id else None
    old = session.claim_id
    if len(named) > 1:
        if field_id:
            session.claim_id = field_id
        listed = ", ".join(named)
        if session.claim_id:
            return (
                f"The question names more than one claim ({listed}); "
                f"investigated {session.claim_id}, the claim in scope."
            )
        return (
            f"The question names more than one claim ({listed}); "
            "no claim was in scope, so the run was not tied to one."
        )
    if named:
        new = named[0]
        notes: list[str] = []
        if field_id and field_id != new:
            notes.append(
                f"The question named {new}; it takes precedence over the claim id "
                f"field ({field_id})."
            )
        if old and old != new:
            notes.append(f"The session claim moved from {old} to {new}.")
        session.claim_id = new
        return " ".join(notes) or None
    if field_id:
        session.claim_id = field_id
    return None


class AskBusyError(RuntimeError):
    """A question is already running (in this session, or on this server)."""


class AskToolRunner(ToolRunner):
    """The API tools, except `search_policy`, which runs the Ask-path search in process."""

    def __init__(self, client: httpx.Client, search: AskPolicySearch) -> None:
        super().__init__(client)
        self._search = search
        self.references: tuple[str, ...] = ()
        self.eval_run_id: str | None = None

    @property
    def search(self) -> AskPolicySearch:
        return self._search

    def execute(self, call: ToolCall, registry: EvidenceRegistry) -> ToolOutput:
        if call.name != "search_policy":
            return super().execute(call, registry)
        problem = self._check_arguments(self._defs[call.name], call.arguments)
        if problem:
            return self._error(call, problem)
        query = str(call.arguments.get("q", "")).strip()
        try:
            k = int(call.arguments.get("k", 5))
        except ValueError:
            return self._error(call, "argument k must be an integer from 1 to 20")
        if not 1 <= len(query) <= 300 or not 1 <= k <= 20:
            return self._error(call, "q must be 1-300 characters and k from 1 to 20")
        payload, _ = self._search.search(
            query, k, references=self.references, eval_run_id=self.eval_run_id
        )
        try:
            trimmed = trim(payload, self._max_chars)
        except ResultTooLargeError:
            return self._error(call, "result too large to show; narrow the request")
        registry.register_result(trimmed)
        return ToolOutput(call.call_id, call.name, dumps(trimmed), False)


@dataclass
class _Ev:
    """What the runtime knows about one citable id, from the tool payload it came from."""

    id: str
    kind: str  # finding | observation | flag | result | search | policy
    tool: str
    subject: str | None
    label: str
    examined: str | None = None
    limits: list[str] = field(default_factory=list)
    check_status: str | None = None
    claim_id: str | None = None
    hit: dict[str, Any] | None = None


def _calls_and_outputs(record: RunRecord) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    """(tool call, tool output) pairs in the order they ran, from the run's own message log."""
    calls: dict[str, dict[str, Any]] = {}
    for m in record.messages:
        if m["role"] == "assistant":
            for c in m["tool_calls"]:
                calls[c["id"]] = c
        elif m["role"] == "tool":
            for o in m["outputs"]:
                call = calls.get(o["id"])
                if call is not None:
                    yield call, o


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _index(record: RunRecord) -> dict[str, _Ev]:
    out: dict[str, _Ev] = {}
    for call, output in _calls_and_outputs(record):
        if output["is_error"]:
            continue
        try:
            payload = json.loads(output["content"])
        except ValueError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("evidence_id"), str):
            claim = payload.get("claim")
            claim_id = _str(claim.get("claim_id")) if isinstance(claim, dict) else None
            _walk(payload, call["name"], claim_id, None, out)
    return out


def _walk(
    node: dict[str, Any], call_name: str, claim_id: str | None, ctx: _Ev | None, out: dict[str, _Ev]
) -> None:
    eid = node.get("evidence_id")
    tool = _str(node.get("tool")) or (ctx.tool if ctx else call_name)
    subject = (
        _str(node.get("subject"))
        or (ctx.subject if ctx else None)
        or _str(node.get("provider_id"))
        or _str(node.get("member_id"))
    )
    here = ctx
    if isinstance(eid, str):
        limits = node.get("limits")
        here = _Ev(
            id=eid,
            kind=_kind(eid, node),
            tool=tool,
            subject=subject,
            label=_label(node, tool, subject or claim_id),
            examined=_str(node.get("examined")) or (ctx.examined if ctx else None),
            limits=[x for x in limits if isinstance(x, str)]
            if isinstance(limits, list)
            else (list(ctx.limits) if ctx else []),
            check_status=_str(node.get("status")) or (ctx.check_status if ctx else None),
            claim_id=claim_id or (subject if subject and CLAIM_ID.fullmatch(subject) else None),
        )
        out[eid] = here
    for key in ("results", "findings", "observations", "flags"):
        items = node.get(key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    _walk(item, call_name, claim_id, here, out)
    hits = node.get("hits")
    if isinstance(hits, list):
        for hit in hits:
            if isinstance(hit, dict) and isinstance(hit.get("chunk_id"), str):
                src = _dict(hit.get("source"))
                out[hit["chunk_id"]] = _Ev(
                    id=hit["chunk_id"],
                    kind="policy",
                    tool="search_policy",
                    subject=None,
                    label=str(src.get("title", "")),
                    hit=hit,
                )


def _kind(eid: str, node: dict[str, Any]) -> str:
    last = eid.rsplit(".", 1)[-1]
    if "hits" in node:
        return "search"
    if last.startswith("f"):
        return "finding"
    if last.startswith("o"):
        return "observation"
    if last.startswith("s"):
        return "flag"
    return "result"


def _label(node: dict[str, Any], tool: str, subject: str | None) -> str:
    if "hits" in node:
        relevance = _dict(node.get("relevance"))
        return (
            f"Policy search ({node.get('mode', '?')}): {len(node['hits'])} passage(s) shown, "
            f"{relevance.get('withheld', 0)} withheld as not close enough to the question"
        )
    summary = _str(node.get("summary"))
    if summary:
        return summary
    if "screen_code" in node:
        return f"Screen {node.get('screen_code')} flagged this claim: {node.get('screen_text', '')}"
    return f"Result of {tool}" + (f" for {subject}" if subject else "")


def _link(ev: _Ev) -> dict[str, str] | None:
    if ev.claim_id:
        return {"view": "claim", "id": ev.claim_id, "check": ev.tool}
    if ev.subject and (PROVIDER_ID.fullmatch(ev.subject) or MEMBER_ID.fullmatch(ev.subject)):
        return {"view": "entity", "id": ev.subject}
    return None


def _source_view(n: int, ev: _Ev) -> dict[str, Any]:
    if ev.kind == "policy" and ev.hit is not None:
        hit, src = ev.hit, _dict(ev.hit.get("source"))
        return {
            "n": n,
            "id": ev.id,
            "kind": "policy",
            "title": str(src.get("title", "")),
            "source_id": str(src.get("source_id", "")),
            "url": str(src.get("url", "")),
            "sha256": str(src.get("sha256", "")),
            "retrieved_at": str(src.get("retrieved_at", "")),
            "page_start": hit.get("page_start"),
            "page_end": hit.get("page_end"),
            "section": str(hit.get("section", "")),
            "text": str(hit.get("text", "")),
            "quotes": [],
        }
    return {
        "n": n,
        "id": ev.id,
        "kind": ev.kind,
        "tool": ev.tool,
        "subject": ev.subject,
        "label": ev.label,
        "examined": ev.examined,
        "limits": ev.limits,
        "check_status": ev.check_status,
        "link": _link(ev),
    }


def _tool_log(record: RunRecord) -> list[dict[str, Any]]:
    """What ran, from the runtime's own log; arguments are shown as data, never acted on."""
    rows: list[dict[str, Any]] = []
    for call, output in _calls_and_outputs(record):
        arguments = dumps(call["arguments"])
        row: dict[str, Any] = {
            "tool": call["name"],
            "arguments": ARGUMENTS_WITHHELD if verdict_match(arguments) else arguments[:200],
            "is_error": output["is_error"],
        }
        if call["name"] == "search_policy" and not output["is_error"]:
            try:
                payload = json.loads(output["content"])
            except ValueError:
                payload = {}
            if isinstance(payload, dict) and isinstance(payload.get("hits"), list):
                rel = _dict(payload.get("relevance"))
                row.update(
                    mode=payload.get("mode"),
                    shown=len(payload["hits"]),
                    withheld=rel.get("withheld", 0),
                    relevance_checked=bool(rel.get("checked")),
                    fallback_reason=payload.get("fallback_reason"),
                )
        rows.append(row)
    return rows


def build_view(record: RunRecord) -> dict[str, Any]:
    """The answer sections, from the validated answer and the run's tool payloads only."""
    answer: FinalAnswer = record.answer
    status = answer.status
    tools = _tool_log(record)
    view: dict[str, Any] = {
        "status": status.value,
        "reason": answer.reason.value,
        "status_label": STATUS_LABEL[status],
        "shown_as_answer": answer.shown_as_answer,
        "message": None,
        "reason_text": REASON_TEXT.get(answer.reason),
        "statements": [],
        "sources": [],
        "limits": [],
        "searched": [],
        "suggestions": [],
        "tools": tools,
        "detail": None,
    }
    if status is Status.OUT_OF_SCOPE:
        claim = record.claim_id or EXAMPLE_CLAIM
        suggestions = [q.format(claim=claim) for q in EVIDENCE_QUESTIONS]
        view.update(
            message=BLOCK_MESSAGE,
            suggestions=suggestions,
            reason_text=None,
            limits=[NOT_A_DETERMINATION],
        )
        return view
    if status is Status.INVALID_OUTPUT:
        if answer.reason is Reason.PROVIDER_ERROR:
            view.update(
                status_label=PROVIDER_FAILED_LABEL,
                message=PROVIDER_FAILED_MESSAGE,
                reason_text=None,  # the message already says it; no duplicate line
                detail=(answer.issues[0] or None) if answer.issues else None,
                limits=[NOT_A_DETERMINATION],
            )
            return view
        view.update(message=INVALID_MESSAGE, limits=[NOT_A_DETERMINATION])
        return view
    if status is Status.INSUFFICIENT_EVIDENCE:
        view.update(
            message=INSUFFICIENT_MESSAGE,
            searched=_searched(tools),
            suggestions=[NARROWER],
            limits=[NOT_A_DETERMINATION],
        )
        return view
    index = _index(record)
    numbers: dict[str, int] = {}
    sources: list[dict[str, Any]] = []

    def number(cid: str) -> int | None:
        ev = index.get(cid)
        if ev is None:
            return None
        if cid not in numbers:
            numbers[cid] = len(sources) + 1
            sources.append(_source_view(numbers[cid], ev))
        return numbers[cid]

    statements = []
    for s in answer.statements:
        refs = [n for n in (number(c) for c in s.citations) if n is not None]
        statements.append({"text": s.text, "refs": refs})
    for q in answer.policy_quotes:
        n = number(q.chunk_id)
        if n is not None:
            sources[n - 1]["quotes"].append(q.quote)
    view.update(statements=statements, sources=sources, limits=_limits(sources, tools))
    return view


def _searched(tools: list[dict[str, Any]]) -> list[str]:
    out = []
    for t in tools:
        line = f"{t['tool']} {t['arguments']}"
        if "shown" in t:
            line += f": {t['shown']} shown, {t['withheld']} withheld"
        if t["is_error"]:
            line += ": returned an error"
        out.append(line)
    return out or ["nothing was searched before the run ended"]


def _limits(sources: list[dict[str, Any]], tools: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for s in sources:
        for limit in s.get("limits") or []:
            if limit not in seen:
                seen.add(limit)
                out.append(limit)
    if any(str(s.get("tool") or "").startswith(CHECK_PREFIXES) for s in sources):
        out.append(SYNTHETIC_RULES)
    searches = [t for t in tools if t["tool"] == "search_policy" and "shown" in t]
    withheld = sum(int(t["withheld"]) for t in searches)
    if withheld:
        out.append(
            f"{withheld} policy passage(s) were found but withheld as not close enough to the "
            "question."
        )
    if any(not t["relevance_checked"] for t in searches):
        out.append(
            "At least one policy search fell back to keyword search; its passages were not "
            "checked for relevance."
        )
    if not searches:
        out.append("No policy source was searched in this turn.")
    out.append(NOT_A_DETERMINATION)
    return out


class AskService:
    busy_error: type[Exception] = AskBusyError

    def __init__(
        self,
        *,
        provider: Provider,
        tools: AskToolRunner,
        guard: CostGuard,
        prompt: Prompt,
        store: SessionStore | None = None,
        limits: Limits | None = None,
        audit: AuditLog | None = None,
        tracer: Tracer | None = None,
        record_dir: Path | None = None,
        session_ceiling: Decimal = SESSION_CEILING_USD,
        server_ceiling: Decimal = SERVER_CEILING_USD,
    ) -> None:
        self._provider, self._tools, self._guard, self._prompt = provider, tools, guard, prompt
        # An empty store has len() 0 and is falsy, so `store or ...` would discard it.
        self._store = store if store is not None else SessionStore()
        self._limits = limits if limits is not None else Limits()
        self._audit, self._tracer, self._record_dir = audit, tracer, record_dir
        self._ceiling = session_ceiling
        self._server_ceiling = server_ceiling
        self._server_spent = Decimal(0)
        self._run_lock = threading.Lock()

    def status(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "provider": self._provider.name,
            "model": self._provider.model_key,
            "prompt_version": self._prompt.version,
            "policy_search": self._tools.search.unavailable is None,
            "policy_search_note": self._tools.search.unavailable,
            "session_ceiling_usd": str(self._ceiling),
            "server_ceiling_usd": str(self._server_ceiling),
            "turn_ceiling_usd": str(min(TURN_CEILING_USD, self._limits.max_usd)),
            "max_turns_kept": MAX_TURNS,
        }

    def reset(self, token: str | None) -> bool:
        return self._store.clear(token)

    def ask(self, token: str | None, question: str, claim_id: str | None) -> dict[str, Any]:
        # The server lock comes first so a busy server creates no session (nothing to evict with).
        if not self._run_lock.acquire(blocking=False):
            raise AskBusyError("another question is running on this server")
        try:
            session, renewed = self._store.get_or_create(token)
            if not self._store.try_begin(session):
                raise AskBusyError("a question is already running in this session")
            try:
                return self._turn(session, renewed, question.strip()[:MAX_QUESTION_CHARS], claim_id)
            finally:
                self._store.end(session)
        finally:
            self._run_lock.release()

    def _spent(self, session: Session) -> Decimal:
        return self._guard.ledger.spent(eval_run_id=session.run_label)

    def _turn(
        self, session: Session, renewed: bool, question: str, claim_id: str | None
    ) -> dict[str, Any]:
        scope_note = _scope_claim(session, question, claim_id)
        spent_before = self._spent(session)
        session_share = self._ceiling - spent_before - SEARCH_RESERVE_USD
        server_share = self._server_ceiling - self._server_spent - SEARCH_RESERVE_USD
        model_share = min(TURN_CEILING_USD, self._limits.max_usd, session_share, server_share)
        previous = session.previous_question
        gate = check_followup(question, session.gate_context)
        if model_share <= 0 and not gate.blocked:
            limit = "server_cost" if server_share <= 0 else "session_cost"
            record = self._ceiling_record(question, session.claim_id, limit)
        else:
            self._tools.references = (question, previous) if previous else (question,)
            self._tools.eval_run_id = session.run_label
            investigator = Investigator(
                self._provider,
                self._tools,
                self._guard,
                self._prompt,
                limits=replace(self._limits, max_usd=max(model_share, Decimal(0))),
                audit=self._audit,
                tracer=self._tracer,
            )
            record = investigator.run(
                question,
                claim_id=session.claim_id,
                eval_run_id=session.run_label,
                previous_question=session.gate_context,
                prior_context=session.prior_context(),
            )
        spent_after = self._spent(session)
        self._server_spent += spent_after - spent_before
        view = build_view(record)
        if record.limit in CEILING_TEXT:
            view.update(reason_text=CEILING_TEXT[record.limit], searched=[])
        answer = record.answer
        session.remember(
            PriorTurn(
                question=question,
                status=answer.status.value,
                statements=tuple(s.text for s in answer.statements),
                claim_id=session.claim_id,
            )
        )
        if self._record_dir is not None:
            self._record_dir.mkdir(parents=True, exist_ok=True)
            path = self._record_dir / f"{session.run_label}-{record.run_id}.json"
            path.write_text(json.dumps(record.to_dict(), indent=1), encoding="utf-8")
        view["run"] = {
            "run_id": record.run_id,
            "provider": record.provider,
            "model": record.model_key,
            "prompt_version": record.prompt_version,
            "model_turns": record.model_calls,
            "tool_calls": sum(1 for t in record.tool_log if not t.get("repeated")),
            "model_cost_usd": str(record.cost_usd),
            "turn_cost_usd": str(spent_after - spent_before),
            "elapsed_s": round(record.elapsed_s, 2),
            "limit": record.limit,
        }
        view["session"] = {
            "token": session.token,
            "renewed": renewed,
            "turn": len(session.turns),
            "claim_id": session.claim_id,
            "spent_usd": str(spent_after),
            "ceiling_usd": str(self._ceiling),
            # States an override or re-scope in plain words, or None; the workbench appends it
            # to the session line so the investigated claim is never silently chosen.
            "note": scope_note,
        }
        return view

    def _ceiling_record(self, question: str, claim_id: str | None, limit: str) -> RunRecord:
        record = RunRecord(
            run_id="ceiling",
            started_at="",
            provider=self._provider.name,
            model_key=self._provider.model_key,
            prompt_version=self._prompt.version,
            prompt_sha256=self._prompt.sha256,
            question=question,
            claim_id=claim_id,
            answer=FinalAnswer(
                Status.INSUFFICIENT_EVIDENCE,
                Reason.BUDGET_LIMIT,
                searched=("nothing searched: " + CEILING_TEXT[limit],),
            ),
            limit=limit,
        )
        if self._audit is not None:
            self._audit.append(
                "agent",
                "investigation",
                claim_id,
                run_id=record.run_id,
                result=record.answer.status.value,
                reason=Reason.BUDGET_LIMIT.value,
                limit=limit,
                question_len=len(question),
                tool_calls=0,
                cost_usd=0.0,
            )
        return record
