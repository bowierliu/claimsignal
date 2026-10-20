"""The Phase 7 evaluation runner: one record per (case, provider, repeat); resumable; gated.

    uv run python -m claims_copilot.evals.runner --split dev --config lexical            # dry run
    uv run python -m claims_copilot.evals.runner --split dev --config lexical --confirm  # spends

A run is a directory under `data/runs/` (gitignored) holding `manifest.json` (what was run and
with which frozen inputs) and one JSON file per job. A job whose file exists is skipped, so an
interrupted run resumes where it stopped and a finished run costs nothing to "run" again. Each job
file holds the full run record (messages, tool log, answer, validator result, tokens, cost) so
scoring and judging never need a provider call to recover what happened.

Rules the runner enforces:

- Every paid call goes through one lock-protected `CostGuard`. The run stops when the run's spend
  reaches its ceiling or Phase 7's total spend reaches the pre-registered ceiling.
- A request the scope gate blocks never reaches a provider (cost $0), as in production.
- A provider error is re-run once (pre-registration `p_run_error_policy`); both attempts are kept.
- Truth is never opened: expected labels come from the case files.
- Planted injection chunks exist only in a per-thread `PlantedPolicyIndex` and only for the
  injection cases; no other case sees them.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import threading
from collections import Counter
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from claims_copilot.agent.answer import Reason, Status
from claims_copilot.agent.loop import Investigator, Limits, RunRecord
from claims_copilot.agent.prompt import Prompt, load_prompt
from claims_copilot.agent.scope import check_request
from claims_copilot.agent.tools import ToolRunner, in_process_client
from claims_copilot.agent.types import Provider
from claims_copilot.budget import Authorization, CostGuard, LedgerEntry, Usage, default_guard
from claims_copilot.evals.casefile import read_cases
from claims_copilot.evals.e2e import CASES_PATH as E2E_PATH
from claims_copilot.evals.e2e import DATASET_INFO_PATH, policy_related
from claims_copilot.evals.handbuilt import HANDBUILT_DIR_NAME, HANDBUILT_FILE, build_handbuilt
from claims_copilot.evals.prereg import load_preregistration
from claims_copilot.evals.safety import CASES_PATH as SAFETY_PATH
from claims_copilot.evals.safety import PlantedPolicyIndex
from claims_copilot.evals.schema import EvalCase, Layer, SafetyKind, Split
from claims_copilot.evals.split import assign_splits
from claims_copilot.evals.unanswerable import CASES_PATH as UNANSWERABLE_PATH
from claims_copilot.project import DATA_DIR, RUNS_DIR
from claims_copilot.secrets import get_secret

PHASE = "p7"
LEXICAL = "lexical"
HYBRID = "hybrid"
CONFIGS = (LEXICAL, HYBRID)
PROVIDER_NAMES = ("openai", "anthropic")
OPENAI_MODEL = "gpt-6-luna"
ANTHROPIC_MODEL = "claude-haiku-5-5"
E2E_DB = DATA_DIR / "eval" / "e2e" / "payer.sqlite"
HANDBUILT_DB = DATA_DIR / "eval" / HANDBUILT_DIR_NAME / HANDBUILT_FILE
# Measured in Phases 5 and 6 (docs/PHASE7_PLAN.md); used only when no measured records exist.
FALLBACK_USD_PER_RUN = {"openai": Decimal("0.0013"), "anthropic": Decimal("0.0022")}
# Assumed extra cost of a hybrid+rerank run: about two uncached searches at about $0.001 each.
HYBRID_EXTRA_USD_PER_RUN = Decimal("0.002")
MAX_CONSECUTIVE_PROVIDER_ERRORS = 6
DEFAULT_WORKERS = 4


# ------------------------------------------------------------------------------ the suite


@dataclass(frozen=True)
class SuiteCase:
    case: EvalCase
    split: Split


def handbuilt_cases() -> list[EvalCase]:
    """The 20 hand-built agent cases. Built into a throwaway directory: the fixture database the
    runs read is not touched, and the scenario list is the same by construction."""
    with tempfile.TemporaryDirectory() as tmp:
        return [s.to_eval_case() for s in build_handbuilt(Path(tmp) / "payer.sqlite")]


def load_suite(*, handbuilt: list[EvalCase] | None = None) -> list[SuiteCase]:
    cases = [
        *read_cases(UNANSWERABLE_PATH),
        *(handbuilt if handbuilt is not None else handbuilt_cases()),
        *read_cases(E2E_PATH),
        *read_cases(SAFETY_PATH),
    ]
    splits = assign_splits(cases)
    return [SuiteCase(c, splits[c.case_id]) for c in cases]


def in_config(case: EvalCase, config: str) -> bool:
    """Which cases a search-mode configuration runs. The lexical configuration runs every case
    (E1, E4). The hybrid configuration runs only the cases whose answer depends on policy search:
    unanswerable questions and policy-related end-to-end cases (E3). Planted injections are
    lexical-only: the planted hit is a worst-case rank-1 exposure in one controlled index."""
    if config == LEXICAL:
        return True
    if config == HYBRID:
        return case.layer is Layer.UNANSWERABLE or (
            case.layer is Layer.E2E and policy_related(case)
        )
    raise ValueError(f"unknown config {config!r}")


@dataclass(frozen=True)
class Job:
    case: EvalCase
    split: Split
    config: str
    provider: str
    repeat: int

    @property
    def filename(self) -> str:
        return f"{self.case.case_id}__{self.provider}__r{self.repeat}.json"

    @property
    def database(self) -> str:
        return "handbuilt" if self.case.layer is Layer.TOOLS_HANDBUILT else "e2e"

    @property
    def planted(self) -> bool:
        return self.case.safety_kind is SafetyKind.PLANTED_INJECTION


def build_jobs(
    suite: Iterable[SuiteCase],
    *,
    split: Split,
    config: str,
    providers: tuple[str, ...],
    repeats: int,
    layers: frozenset[Layer] | None = None,
) -> list[Job]:
    """Ordered by repeat, then case, then provider, so a run stopped early is balanced."""
    chosen = [
        s
        for s in suite
        if s.split is split
        and in_config(s.case, config)
        and (layers is None or s.case.layer in layers)
    ]
    return [
        Job(s.case, s.split, config, provider, repeat)
        for repeat in range(1, repeats + 1)
        for s in chosen
        for provider in providers
    ]


# ------------------------------------------------------------------------------ estimates


@dataclass(frozen=True)
class Estimate:
    jobs: int
    gated: int
    expected_usd: Decimal
    by_provider: dict[str, int]
    basis: dict[str, str]


def measured_cost_per_run(runs_dir: Path = RUNS_DIR) -> dict[str, Decimal]:
    """Mean cost of runs that reached a model, by provider, from earlier job and smoke records."""
    totals: dict[str, list[Decimal]] = {}
    for path in sorted(runs_dir.glob("*/*.json")) if runs_dir.is_dir() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        record = data.get("record", data) if isinstance(data, dict) else None
        if not isinstance(record, dict) or "cost_usd" not in record or "provider" not in record:
            continue
        if record.get("limit") == "scope_gate":
            continue
        totals.setdefault(str(record["provider"]), []).append(Decimal(str(record["cost_usd"])))
    return {p: sum(v, Decimal(0)) / len(v) for p, v in totals.items() if v}


def estimate(jobs: Iterable[Job], per_run: dict[str, Decimal], config: str) -> Estimate:
    n = 0
    gated = 0
    total = Decimal(0)
    by_provider: Counter[str] = Counter()
    for job in jobs:
        n += 1
        if check_request(job.case.question).blocked:
            gated += 1
            continue
        by_provider[job.provider] += 1
        cost = per_run.get(job.provider) or FALLBACK_USD_PER_RUN[job.provider]
        total += cost + (HYBRID_EXTRA_USD_PER_RUN if config == HYBRID else Decimal(0))
    basis = {
        p: ("measured mean" if p in per_run else "plan figure (no measured records)")
        for p in by_provider
    }
    return Estimate(n, gated, total, dict(by_provider), basis)


# ------------------------------------------------------------------------------ guard


class LockedGuard(CostGuard):
    """CostGuard that is safe to share between worker threads: the ledger is read and appended
    under one lock, so a reader never sees a half-written line and the caps see every entry."""

    def __init__(self, base: CostGuard) -> None:
        super().__init__(base.caps, base.prices, base.ledger)
        self._lock = threading.RLock()

    def authorize(self, **kw: Any) -> Authorization:
        with self._lock:
            return super().authorize(**kw)

    def record(self, auth: Authorization, usage: Usage | None, *, status: Any) -> LedgerEntry:
        with self._lock:
            return super().record(auth, usage, status=status)

    def spent(self, **kw: Any) -> Decimal:
        with self._lock:
            return self.ledger.spent(**kw)


# ------------------------------------------------------------------------------ rigs


@dataclass
class Rig:
    """What one worker needs for one job: the tool runner and, for planted cases, the index to
    switch on."""

    runner: ToolRunner
    planted: PlantedPolicyIndex | None = None


RigFactory = Callable[[Job], Rig]
ProviderFactory = Callable[[str], Provider]


class LiveRigs:
    """Builds the in-process API stacks lazily, one set per worker thread (SQLite handles and the
    planted index are per thread). Policy indexes are shared and read-only, apart from the
    hybrid pipeline's own locks."""

    def __init__(self, guard: CostGuard, eval_run_id: str) -> None:
        self._guard = guard
        self._eval_run_id = eval_run_id
        self._local = threading.local()
        self._lock = threading.Lock()
        self._shared: dict[str, Any] = {}

    def _index(self, config: str) -> Any:
        from claims_copilot.api.policy import load_policy_index

        with self._lock:
            if config not in self._shared:
                if config == LEXICAL:
                    index = load_policy_index(mode="lexical")
                else:
                    index = load_policy_index(
                        mode="hybrid",
                        guard=self._guard,
                        phase=PHASE,
                        eval_run_id=self._eval_run_id,
                    )
                    if index is not None and not index.hybrid_enabled:
                        raise RuntimeError("hybrid search is unavailable; refusing to fall back")
                if index is None:
                    raise RuntimeError("the policy corpus is not ingested (data/chunks missing)")
                self._shared[config] = index
            return self._shared[config]

    def __call__(self, job: Job) -> Rig:
        from claims_copilot.api.app import create_app

        cache: dict[tuple[str, str, bool], Rig] = self._local.__dict__.setdefault("rigs", {})
        key = (job.database, job.config, job.planted)
        if key not in cache:
            payer = HANDBUILT_DB if job.database == "handbuilt" else E2E_DB
            policy: Any = self._index(job.config)
            planted = PlantedPolicyIndex(policy) if job.planted else None
            index = planted or policy
            app = create_app(payer, policy_loader=lambda: index)
            cache[key] = Rig(ToolRunner(in_process_client(app)), planted)
        return cache[key]


def make_providers() -> dict[str, Provider]:
    from claims_copilot.agent.providers import AnthropicProvider, OpenAIProvider

    return {
        "openai": OpenAIProvider(get_secret("OPENAI_API_KEY") or "", OPENAI_MODEL),
        "anthropic": AnthropicProvider(get_secret("ANTHROPIC_API_KEY") or "", ANTHROPIC_MODEL),
    }


# ------------------------------------------------------------------------------ the run


@dataclass(frozen=True)
class Outcome:
    done: int
    skipped: int
    provider_errors: int
    stopped: str | None
    by_status: dict[str, int]
    spent_usd: Decimal


def provider_error(record: RunRecord) -> bool:
    return (
        record.answer.status is Status.INVALID_OUTPUT
        and record.answer.reason is Reason.PROVIDER_ERROR
    )


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


class EvalRunner:
    def __init__(
        self,
        run_dir: Path,
        *,
        guard: LockedGuard,
        rigs: RigFactory,
        providers: ProviderFactory,
        prompt: Prompt,
        eval_run_id: str,
        run_ceiling: Decimal,
        phase_ceiling: Decimal,
        limits: Limits | None = None,
        workers: int = DEFAULT_WORKERS,
        echo: Callable[[str], None] = lambda _m: None,
    ) -> None:
        self._dir = run_dir
        self._guard = guard
        self._rigs = rigs
        self._providers = providers
        self._prompt = prompt
        self._eval_run_id = eval_run_id
        self._run_ceiling = run_ceiling
        self._phase_ceiling = phase_ceiling
        self._limits = limits or Limits()
        self._workers = max(1, workers)
        self._echo = echo
        self._lock = threading.Lock()
        self._stop_reason: str | None = None
        self._streak = 0

    # -- stop conditions

    def _stop(self, reason: str) -> None:
        with self._lock:
            if self._stop_reason is None:
                self._stop_reason = reason
                self._echo(f"STOP: {reason}")

    def _check_ceilings(self) -> None:
        if self._guard.spent(eval_run_id=self._eval_run_id) >= self._run_ceiling:
            self._stop(f"this run's spend reached its ${self._run_ceiling} ceiling")
        elif self._guard.spent(phase=PHASE) >= self._phase_ceiling:
            self._stop(f"Phase 7 spend reached its ${self._phase_ceiling} ceiling")

    # -- one job

    def _one(self, job: Job) -> tuple[str, RunRecord | None]:
        path = self._dir / job.filename
        if path.exists():
            return "skipped", None
        if self._stop_reason is not None:
            return "not_started", None
        rig = self._rigs(job)
        provider = self._providers(job.provider)
        investigator = Investigator(
            provider, rig.runner, self._guard, self._prompt, limits=self._limits, phase=PHASE
        )
        attempts: list[RunRecord] = []
        if rig.planted is not None:
            rig.planted.activate(job.case.case_id)
        try:
            for _ in range(2):
                record = investigator.run(
                    job.case.question, claim_id=job.case.claim_id, eval_run_id=self._eval_run_id
                )
                attempts.append(record)
                if record.limit == "guard_refused":
                    self._stop("CostGuard refused a call (a cap was reached)")
                    return "not_started", record
                if not provider_error(record):
                    break
        finally:
            if rig.planted is not None:
                rig.planted.activate(None)
        final = attempts[-1]
        _write_atomic(
            path,
            {
                "job": {
                    "case_id": job.case.case_id,
                    "split": job.split.value,
                    "config": job.config,
                    "provider": job.provider,
                    "repeat": job.repeat,
                    "planted": job.planted,
                },
                "case": job.case.to_dict(),
                "attempts": len(attempts),
                "record": final.to_dict(),
                "earlier_attempts": [a.to_dict() for a in attempts[:-1]],
            },
        )
        return "done", final

    def _run_job(self, job: Job) -> tuple[Job, str, RunRecord | None]:
        try:
            outcome, record = self._one(job)
        except Exception as exc:
            # A broken job must not kill the others; say what kind of error, never a body.
            self._stop(f"unexpected {type(exc).__name__} on {job.filename}")
            return job, "not_started", None
        if record is not None and outcome == "done":
            with self._lock:
                self._streak = self._streak + 1 if provider_error(record) else 0
                streak = self._streak
            self._echo(
                f"{job.provider:<9} {job.case.case_id:<8} r{job.repeat} "
                f"{record.answer.status.value:<22} {record.answer.reason.value:<19} "
                f"calls={record.model_calls} ${record.cost_usd} {record.elapsed_s:.1f}s"
            )
            if streak >= MAX_CONSECUTIVE_PROVIDER_ERRORS:
                self._stop(f"{streak} provider errors in a row")
            self._check_ceilings()
        return job, outcome, record

    def run(self, jobs: list[Job], manifest: dict[str, Any]) -> Outcome:
        self._dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self._dir / "manifest.json"
        if not manifest_path.exists():
            _write_atomic(manifest_path, manifest)
        self._check_ceilings()
        counts: Counter[str] = Counter()
        statuses: Counter[str] = Counter()
        errors = 0
        with ThreadPoolExecutor(max_workers=self._workers) as pool:
            for _job, outcome, record in pool.map(self._run_job, jobs):
                counts[outcome] += 1
                if record is not None and outcome == "done":
                    statuses[record.answer.status.value] += 1
                    errors += provider_error(record)
        return Outcome(
            done=counts["done"],
            skipped=counts["skipped"],
            provider_errors=errors,
            stopped=self._stop_reason,
            by_status=dict(statuses),
            spent_usd=self._guard.spent(eval_run_id=self._eval_run_id),
        )


# ------------------------------------------------------------------------------ reading runs


def read_job_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "record" not in data or "job" not in data:
        raise ValueError(f"not a job record: {path.name}")
    return data


def read_run(run_dir: Path) -> list[dict[str, Any]]:
    return [read_job_file(p) for p in sorted(run_dir.glob("*__*__r*.json"))]


# ------------------------------------------------------------------------------ CLI


def _verify_e2e_database(path: Path) -> str:
    from claims_copilot.tools.repository import Repository

    repo = Repository.open(path)
    try:
        found = repo.meta("payer_hash")
    finally:
        repo.close()
    expected = json.loads(DATASET_INFO_PATH.read_text(encoding="utf-8"))["payer_sha256"]
    if found != expected:
        raise SystemExit("the e2e database does not match eval/phase7_e2e_dataset.json")
    return str(found)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="claims_copilot.evals.runner", description=__doc__)
    parser.add_argument("--split", choices=[s.value for s in Split], required=True)
    parser.add_argument("--config", choices=CONFIGS, default=LEXICAL)
    parser.add_argument("--providers", choices=[*PROVIDER_NAMES, "both"], default="both")
    parser.add_argument("--layers", default="", help="comma-separated layers (default: all)")
    parser.add_argument("--repeats", type=int, default=0, help="default: the pre-registered 3")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--run-name", default="")
    parser.add_argument("--confirm", action="store_true", help="spend money (default: dry run)")
    args = parser.parse_args(argv)

    prereg = load_preregistration()
    repeats = args.repeats or prereg.repeats
    providers = PROVIDER_NAMES if args.providers == "both" else (args.providers,)
    layers = frozenset(Layer(x) for x in args.layers.split(",") if x) or None
    run_name = args.run_name or f"p7-{args.split}-{args.config}"
    run_dir = RUNS_DIR / run_name

    suite = load_suite()
    jobs = build_jobs(
        suite,
        split=Split(args.split),
        config=args.config,
        providers=providers,
        repeats=repeats,
        layers=layers,
    )
    todo = [j for j in jobs if not (run_dir / j.filename).exists()]
    guard = LockedGuard(default_guard())
    est = estimate(todo, measured_cost_per_run(), args.config)
    spent_phase = guard.spent(phase=PHASE)
    remaining = prereg.phase_ceiling_usd - spent_phase
    print(f"run: {run_name}  split={args.split} config={args.config} repeats={repeats}")
    print(
        f"jobs: {len(jobs)} planned, {len(jobs) - len(todo)} already recorded, {len(todo)} to run"
    )
    print(
        f"  of which {est.gated} are stopped by the scope gate at $0; paid runs {est.by_provider}"
    )
    print(f"expected spend: ${est.expected_usd:.4f} ({est.basis})")
    print(
        f"Phase 7 spent so far ${spent_phase}; ceiling ${prereg.phase_ceiling_usd}; "
        f"remaining ${remaining}"
    )
    if not args.confirm:
        print("dry run only; re-run with --confirm to spend.")
        return 0
    if est.expected_usd > remaining:
        print("refusing: the estimate exceeds the remaining ceiling; shrink the run first.")
        return 3
    missing = [
        k
        for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
        if not get_secret(k) and k.lower().startswith(tuple(providers))
    ]
    if missing:
        print(f"refusing: {', '.join(missing)} is empty. Set it in .env (never in chat).")
        return 2

    dataset_hash = _verify_e2e_database(E2E_DB)
    prompt = load_prompt()
    provider_map = make_providers()
    runner = EvalRunner(
        run_dir,
        guard=guard,
        rigs=LiveRigs(guard, run_name),
        providers=lambda name: provider_map[name],
        prompt=prompt,
        eval_run_id=run_name,
        run_ceiling=min(prereg.phase_ceiling_usd, guard.caps.eval_run_usd),
        phase_ceiling=prereg.phase_ceiling_usd,
        workers=args.workers,
        echo=print,
    )
    manifest = {
        "run": run_name,
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "split": args.split,
        "config": args.config,
        "repeats": repeats,
        "providers": {n: provider_map[n].model_key for n in providers},
        "prompt": {"version": prompt.version, "sha256": prompt.sha256},
        "preregistration_sha256": prereg.sha256,
        "e2e_payer_hash": dataset_hash,
        "jobs": len(jobs),
    }
    outcome = runner.run(todo, manifest)
    print(
        f"done: {outcome.done} recorded, {outcome.skipped} skipped, {outcome.provider_errors} "
        f"provider errors; statuses {outcome.by_status}; run spend ${outcome.spent_usd}"
    )
    if outcome.stopped:
        print(f"stopped early: {outcome.stopped}; re-run the same command to resume.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
