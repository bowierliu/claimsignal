"""The faithfulness and conflict judge (Phase 7), used only after calibration against owner labels.

For each shown answer with statements, the judge sees every statement and the exact text it cites
and labels each one under `eval/rubrics/faithfulness_v1.md` (the rubric the owner labels with). For
a `CONFLICTING_EVIDENCE` answer it also gives the `conflict_v1` label and pattern. An answer from
one provider is judged by the other provider's model, so no model grades its own writing.

Judge output is untrusted data: it is parsed against a strict schema and a bad parse is recorded
as a failure, never turned into a guessed label. Sources and statements are passed inside tags and
escaped, and the prompt says they are data. Every call goes through CostGuard.

    uv run python -m claims_copilot.evals.judge --run p7-dev-lexical            # dry run
    uv run python -m claims_copilot.evals.judge --run p7-dev-lexical --confirm
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import html
import json
import threading
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from claims_copilot.agent.prompt import Prompt, load_prompt
from claims_copilot.agent.types import Provider, ProviderError, UserMessage
from claims_copilot.budget import (
    ApprovalRequiredError,
    BudgetExceededError,
    Usage,
    default_guard,
    estimate_tokens,
)
from claims_copilot.evals.runner import (
    ANTHROPIC_MODEL,
    OPENAI_MODEL,
    PHASE,
    LockedGuard,
    make_providers,
    read_run,
)
from claims_copilot.project import REPO_ROOT, RUNS_DIR
from claims_copilot.secrets import get_secret

PROMPT_VERSION = "judge_v1"
RUBRIC_DIR = REPO_ROOT / "eval" / "rubrics"
SOURCE_CHARS = 900  # the owner's sheet uses the same cut, so judge and human see the same text
MAX_OUTPUT_TOKENS = 2000
LABELS = ("SUPPORTED", "PARTLY", "NOT_SUPPORTED", "CANNOT_TELL")
CONFLICT_LABELS = ("WARRANTED", "NOT_WARRANTED", "NOT_APPLICABLE")
PATTERNS = ("FLAG_VS_CHECK", "OTHER", "NOT_APPLICABLE")
N_A = "NOT_APPLICABLE"
JUDGE_OF = {"openai": "anthropic", "anthropic": "openai"}  # who judges whose answers
CONFLICTING = "CONFLICTING_EVIDENCE"


class JudgeParseError(ValueError):
    """The judge's output does not match the schema. The message never repeats the output."""


# ------------------------------------------------------------------------------ sources


def _walk(node: Any, out: dict[str, str]) -> None:
    if isinstance(node, dict):
        evidence_id = node.get("evidence_id")
        if isinstance(evidence_id, str):
            out.setdefault(evidence_id, json.dumps(node, ensure_ascii=False, sort_keys=True))
        chunk_id = node.get("chunk_id")
        if isinstance(chunk_id, str) and isinstance(node.get("text"), str):
            out.setdefault(chunk_id, str(node["text"]))
        for value in node.values():
            _walk(value, out)
    elif isinstance(node, list):
        for value in node:
            _walk(value, out)


def source_index(record: dict[str, Any]) -> dict[str, str]:
    """Citation id -> the text of what it points to, rebuilt from the run's recorded tool outputs
    (the same text the model was shown). Ids the model invented are simply absent."""
    out: dict[str, str] = {}
    for message in record.get("messages", []):
        if message.get("role") != "tool":
            continue
        for output in message.get("outputs", []):
            if output.get("is_error"):
                continue
            try:
                payload = json.loads(output.get("content", ""))
            except ValueError:
                continue
            _walk(payload, out)
    return out


def clip(text: str, limit: int = SOURCE_CHARS) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]} [... {len(text) - limit} more characters not shown]"


@dataclass(frozen=True)
class Item:
    """One statement with the text of each source it cites (None: the id does not resolve)."""

    n: int
    text: str
    citations: tuple[str, ...]
    sources: tuple[tuple[str, str | None], ...]


def answer_items(record: dict[str, Any]) -> list[Item]:
    answer = record["answer"]
    if not answer.get("shown_as_answer", True):
        return []
    index = source_index(record)
    items = []
    for n, statement in enumerate(answer.get("summary", []), start=1):
        citations = tuple(statement["citations"])
        items.append(
            Item(
                n,
                statement["text"],
                citations,
                tuple((c, index.get(c)) for c in citations),
            )
        )
    return items


# ------------------------------------------------------------------------------ messages


def system_text(prompt: Prompt) -> str:
    """The judge prompt with the two rubrics written into it (the owner's rubric, unchanged)."""
    faithful = (RUBRIC_DIR / "faithfulness_v1.md").read_text(encoding="utf-8")
    conflict = (RUBRIC_DIR / "conflict_v1.md").read_text(encoding="utf-8")
    return prompt.text.replace("{{FAITHFULNESS_RUBRIC}}", faithful).replace(
        "{{CONFLICT_RUBRIC}}", conflict
    )


def render_answer(status: str, items: Iterable[Item]) -> str:
    def esc(text: str) -> str:
        return html.escape(text, quote=False)

    lines = [f'<answer status="{esc(status)}">']
    for item in items:
        lines.append(f'<statement n="{item.n}">')
        lines.append(f"<text>{esc(item.text)}</text>")
        for citation, text in item.sources:
            if text is None:
                lines.append(f'<source id="{esc(citation)}" missing="true"/>')
            else:
                lines.append(f'<source id="{esc(citation)}">{esc(clip(text))}</source>')
        lines.append("</statement>")
    lines.append("</answer>")
    return "\n".join(lines)


def judge_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "labels": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "n": {"type": "integer"},
                        "label": {"type": "string", "enum": list(LABELS)},
                    },
                    "required": ["n", "label"],
                    "additionalProperties": False,
                },
            },
            "conflict_label": {"type": "string", "enum": list(CONFLICT_LABELS)},
            "conflict_pattern": {"type": "string", "enum": list(PATTERNS)},
        },
        "required": ["labels", "conflict_label", "conflict_pattern"],
        "additionalProperties": False,
    }


@dataclass(frozen=True)
class Judgment:
    labels: dict[int, str]
    conflict_label: str
    conflict_pattern: str


def parse_judgment(text: str, n_statements: int, status: str) -> Judgment:
    try:
        data = json.loads(text)
    except (ValueError, RecursionError):
        raise JudgeParseError("output is not valid JSON") from None
    if not isinstance(data, dict) or set(data) != {"labels", "conflict_label", "conflict_pattern"}:
        raise JudgeParseError("output keys do not match the schema")
    rows = data["labels"]
    if not isinstance(rows, list):
        raise JudgeParseError("labels must be a list")
    labels: dict[int, str] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"n", "label"}:
            raise JudgeParseError("bad label row")
        n, label = row["n"], row["label"]
        if not isinstance(n, int) or isinstance(n, bool) or label not in LABELS or n in labels:
            raise JudgeParseError("bad or repeated label")
        labels[n] = label
    if set(labels) != set(range(1, n_statements + 1)):
        raise JudgeParseError("labels do not cover exactly the statements given")
    conflict, pattern = data["conflict_label"], data["conflict_pattern"]
    if conflict not in CONFLICT_LABELS or pattern not in PATTERNS:
        raise JudgeParseError("conflict fields are not allowed values")
    if status == CONFLICTING:
        if conflict == N_A or pattern == N_A:
            raise JudgeParseError("a conflicting answer needs both conflict fields")
    elif conflict != N_A or pattern != N_A:
        raise JudgeParseError("conflict fields must be NOT_APPLICABLE for this status")
    return Judgment(labels, conflict, pattern)


# ------------------------------------------------------------------------------ the judge


@dataclass(frozen=True)
class JudgeResult:
    judgment: Judgment | None
    error: str | None
    judge_model: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    stopped: bool = False  # a spend cap refused the call; nothing should be written


class Judge:
    def __init__(
        self,
        provider: Provider,
        guard: LockedGuard,
        prompt: Prompt,
        *,
        eval_run_id: str,
    ) -> None:
        self._provider = provider
        self._guard = guard
        self._prompt = prompt
        self._system = system_text(prompt)
        self._schema = judge_schema()
        self._eval_run_id = eval_run_id

    @property
    def model_key(self) -> str:
        return self._provider.model_key

    def estimate(self, message: str) -> Usage:
        return Usage(
            estimate_tokens(self._system + message + json.dumps(self._schema)), MAX_OUTPUT_TOKENS
        )

    def judge(self, record: dict[str, Any]) -> JudgeResult | None:
        """None when there is nothing to judge (no statements)."""
        items = answer_items(record)
        if not items:
            return None
        status = record["answer"]["status"]
        message = render_answer(status, items)
        estimate = self.estimate(message)
        try:
            turn = self._guard.call(
                functools.partial(
                    self._provider.complete,
                    system=self._system,
                    messages=[UserMessage(message)],
                    tools=[],
                    schema=self._schema,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                    allow_tools=False,
                ),
                usage_of=lambda t: t.usage,
                phase=PHASE,
                model_key=self._provider.model_key,
                purpose="p7 judge",
                estimated_usage=estimate,
                eval_run_id=self._eval_run_id,
            )
        except (BudgetExceededError, ApprovalRequiredError):
            return JudgeResult(
                None, "spend cap refused the call", self.model_key, 0, 0, Decimal(0), True
            )
        except ProviderError as exc:
            return JudgeResult(
                None, f"provider error: {str(exc)[:120]}", self.model_key, 0, 0, Decimal(0)
            )
        cost = self._guard.cost(self._provider.model_key, turn.usage)
        try:
            judgment = parse_judgment(turn.text, len(items), status)
        except JudgeParseError as exc:
            return JudgeResult(
                None,
                f"parse: {exc}",
                self.model_key,
                turn.usage.input_tokens,
                turn.usage.output_tokens,
                cost,
            )
        return JudgeResult(
            judgment,
            None,
            self.model_key,
            turn.usage.input_tokens,
            turn.usage.output_tokens,
            cost,
        )


def prompt_fingerprint(prompt: Prompt) -> str:
    return hashlib.sha256(system_text(prompt).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------ batch


def judgment_path(judge_dir: Path, job_file_stem: str) -> Path:
    return judge_dir / f"{job_file_stem}.json"


def run_judging(
    rows: list[dict[str, Any]],
    judge_dir: Path,
    judges: dict[str, Judge],
    *,
    workers: int = 4,
    echo: Callable[[str], None] = lambda _m: None,
) -> dict[str, int]:
    """Judge each row's answer with the other provider's judge; one file per answer, resumable."""
    judge_dir.mkdir(parents=True, exist_ok=True)
    counts = {"judged": 0, "skipped": 0, "no_statements": 0, "parse_errors": 0, "stopped": 0}
    lock = threading.Lock()
    stop = threading.Event()

    def one(row: dict[str, Any]) -> None:
        job = row["job"]
        stem = f"{job['case_id']}__{job['provider']}__r{job['repeat']}"
        path = judgment_path(judge_dir, stem)
        if path.exists():
            with lock:
                counts["skipped"] += 1
            return
        if stop.is_set():
            return
        judge = judges[JUDGE_OF[job["provider"]]]
        result = judge.judge(row["record"])
        with lock:
            if result is None:
                counts["no_statements"] += 1
                return
            if result.stopped:
                counts["stopped"] += 1
                stop.set()
                echo("STOP: a spend cap refused a judge call")
                return
            counts["judged" if result.judgment else "parse_errors"] += 1
        j = result.judgment
        payload = {
            "job": job,
            "judge_model": result.judge_model,
            "prompt_version": PROMPT_VERSION,
            "error": result.error,
            "labels": {str(n): v for n, v in j.labels.items()} if j else None,
            "conflict_label": j.conflict_label if j else None,
            "conflict_pattern": j.conflict_pattern if j else None,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cost_usd": str(result.cost_usd),
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        tmp.replace(path)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        list(pool.map(one, rows))
    return counts


def read_judgments(judge_dir: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(judge_dir.glob("*.json")):
        out[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return out


# ------------------------------------------------------------------------------ CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="claims_copilot.evals.judge", description=__doc__)
    parser.add_argument("--run", required=True, help="run directory name under data/runs/")
    parser.add_argument(
        "--only", default="", help="file with job-file stems to judge, one per line"
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--confirm", action="store_true", help="spend money (default: dry run)")
    args = parser.parse_args(argv)

    run_dir = RUNS_DIR / args.run
    rows = read_run(run_dir)
    if args.only:
        wanted = set(Path(args.only).read_text(encoding="utf-8").split())
        rows = [
            r
            for r in rows
            if f"{r['job']['case_id']}__{r['job']['provider']}__r{r['job']['repeat']}" in wanted
        ]
    judge_dir = run_dir / "judgments"
    prompt = load_prompt(PROMPT_VERSION)
    guard = LockedGuard(default_guard())
    todo = [
        r
        for r in rows
        if answer_items(r["record"])
        and not judgment_path(
            judge_dir, f"{r['job']['case_id']}__{r['job']['provider']}__r{r['job']['repeat']}"
        ).exists()
    ]
    total = Decimal(0)
    for r in todo:
        key = f"{JUDGE_OF[r['job']['provider']]}/" + (
            ANTHROPIC_MODEL if r["job"]["provider"] == "openai" else OPENAI_MODEL
        )
        message = render_answer(r["record"]["answer"]["status"], answer_items(r["record"]))
        usage = Usage(
            estimate_tokens(system_text(prompt) + message) // 2,  # tokens ~ 1 per 3 bytes
            300,
        )
        total += guard.cost(key, usage)
    print(f"judging {len(todo)} answers from {args.run} ({len(rows)} recorded runs)")
    print(f"prompt {PROMPT_VERSION} fingerprint {prompt_fingerprint(prompt)[:12]}")
    print(f"rough estimate ${total:.4f}; Phase 7 spent so far ${guard.spent(phase=PHASE)}")
    if not args.confirm:
        print("dry run only; re-run with --confirm to spend.")
        return 0
    if not get_secret("OPENAI_API_KEY") or not get_secret("ANTHROPIC_API_KEY"):
        print("refusing: a provider key is empty. Set it in .env (never in chat).")
        return 2
    providers = make_providers()
    judges = {
        name: Judge(providers[name], guard, prompt, eval_run_id=f"{args.run}-judge")
        for name in providers
    }
    counts = run_judging(todo, judge_dir, judges, workers=args.workers, echo=print)
    print(f"done: {counts}; Phase 7 spent ${guard.spent(phase=PHASE)}")
    return 1 if counts["stopped"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
