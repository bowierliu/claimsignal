"""Scorecard: how well do the tools recover the seeded cases? (Evaluation only.)

Run: `uv run python -m claims_copilot.tools.score --data data/synth [--label NAME] [--json PATH]`

This is the only module in the tools package that opens `truth.sqlite`; a test enforces that.
It runs the tools over every claim (and every provider with enough visit lines), then compares
what they raised with the labels:

- positives: claims in a seeded anomaly case; decoys: claims in a look-alike case that is fine;
  clean: every other claim.
- precision = true positives / everything raised; recall = true positives / positives;
  "decoys raised" and "clean raised" are the false alarms, reported separately.
- The near-match duplicate tiers are observations, not findings; their rates are reported so the
  cost of that looser rule is visible.

Nothing here tunes anything. The printed parameters and their hash are what produced the numbers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from claims_copilot.project import REPO_ROOT, SYNTH_OUT_DIR
from claims_copilot.synth.anomalies import (
    DATE_ANOMALY,
    DUPLICATE,
    EXCESS_UNITS,
    OUTLIER,
    UNBUNDLING,
)
from claims_copilot.synth.store import PAYER_FILE, TRUTH_FILE
from claims_copilot.tools import duplicates, edits, patterns
from claims_copilot.tools.codes import validate_claim_codes
from claims_copilot.tools.duplicates import find_duplicate_candidates
from claims_copilot.tools.edits import check_bundling, check_service_dates, check_unit_limits
from claims_copilot.tools.icd import IcdCodeSet, IcdSourceUnavailableError, load_icd_codes
from claims_copilot.tools.patterns import PeerBook, provider_intensity
from claims_copilot.tools.repository import Repository
from claims_copilot.tools.rules import SyntheticRules

CLAIM_LEVEL: dict[str, frozenset[str]] = {
    DUPLICATE: frozenset({duplicates.EXACT_CHECK}),
    UNBUNDLING: frozenset({edits.BUNDLE_CHECK}),
    EXCESS_UNITS: frozenset({edits.UNIT_CHECK}),
    DATE_ANOMALY: frozenset({edits.DATE_CHECK, edits.WINDOW_CHECK}),
}
LINE_LEVEL = (UNBUNDLING, EXCESS_UNITS, DATE_ANOMALY)
SCREEN_TYPE = {
    "SCR01": DUPLICATE,
    "SCR02": UNBUNDLING,
    "SCR03": EXCESS_UNITS,
    "SCR04": OUTLIER,
    "SCR05": DATE_ANOMALY,
}
GROUPS = ("positive", "decoy", "clean")


@dataclass
class TypeScore:
    anomaly_type: str
    level: str  # "claim" or "provider"
    positives: int = 0
    decoys: int = 0
    clean: int = 0
    true_positives: int = 0
    decoys_raised: int = 0
    clean_raised: int = 0
    line_cases: int = 0  # cases with labelled lines (line-level types)
    line_cases_localised: int = 0  # every labelled line appears in a finding's line refs
    missed: list[str] = field(default_factory=list)
    decoys_raised_ids: list[str] = field(default_factory=list)
    clean_raised_ids: list[str] = field(default_factory=list)

    @property
    def raised(self) -> int:
        return self.true_positives + self.decoys_raised + self.clean_raised

    @property
    def precision(self) -> float | None:
        return self.true_positives / self.raised if self.raised else None

    @property
    def recall(self) -> float | None:
        return self.true_positives / self.positives if self.positives else None


@dataclass
class Scorecard:
    label: str
    payer_hash: str
    params: dict[str, str]
    params_hash: str
    icd_checked: bool
    claims_scored: int
    types: dict[str, TypeScore]
    near_rates: dict[str, dict[str, int]]  # tier -> group -> claims with that observation
    group_sizes: dict[str, int]
    other_findings: dict[str, int]  # checks with no labelled counterpart: count of claims
    flag_triage: dict[str, dict[str, int]]  # screen -> measure -> count
    providers_not_scored: dict[str, int]


def parameters() -> dict[str, str]:
    return {
        "ruleset": SyntheticRules.name,
        "z_threshold": str(patterns.Z_THRESHOLD),
        "min_visit_lines": str(patterns.MIN_VISIT_LINES),
        "min_peers": str(patterns.MIN_PEERS),
        "mad_floor": str(patterns.MAD_FLOOR),
        "near_match_days": str(duplicates.NEAR_DAYS),
    }


def params_hash(params: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:12]


def _open_truth(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def _truth(con: sqlite3.Connection) -> list[tuple[str, str, bool, str, list[str], list[str]]]:
    claims: dict[str, list[str]] = defaultdict(list)
    for aid, cid in con.execute("SELECT anomaly_id, claim_id FROM truth_claim ORDER BY 1, seq"):
        claims[aid].append(cid)
    lines: dict[str, list[str]] = defaultdict(list)
    for aid, lid in con.execute("SELECT anomaly_id, line_id FROM truth_line ORDER BY 1, seq"):
        lines[aid].append(lid)
    return [
        (aid, atype, bool(decoy), provider, claims[aid], lines[aid])
        for aid, atype, decoy, provider in con.execute(
            "SELECT anomaly_id, anomaly_type, is_decoy, provider_id FROM anomaly_truth ORDER BY 1"
        )
    ]


def score_dataset(data_dir: Path, label: str = "") -> Scorecard:
    repo = Repository.open(data_dir / PAYER_FILE)
    truth_con = _open_truth(data_dir / TRUTH_FILE)
    cases = _truth(truth_con)
    ph = repo._con.execute("SELECT value FROM meta WHERE key='payer_hash'").fetchone()[0]
    rules = SyntheticRules(repo)
    icd: IcdCodeSet | None
    try:
        icd = load_icd_codes()
    except IcdSourceUnavailableError:
        icd = None

    # --- run the tools over every claim --------------------------------------------------
    raised: dict[str, dict[str, set[str]]] = {}  # claim -> check -> line ids it cites
    near: dict[str, set[str]] = defaultdict(set)  # tier -> claims
    claim_ids = repo.claim_ids()
    for cid in claim_ids:
        per: dict[str, set[str]] = {}
        results = (
            check_bundling(repo, rules, cid),
            check_unit_limits(repo, rules, cid),
            check_service_dates(repo, cid),
            find_duplicate_candidates(repo, cid),
            validate_claim_codes(repo, cid, icd),
        )
        for res in results:
            for f in res.findings:
                per.setdefault(f.check, set()).update(f.ids("line"))
            for o in res.observations:
                if o.check in (duplicates.NEAR_PROVIDER, duplicates.NEAR_DATE):
                    near[o.check].add(cid)
        if per:
            raised[cid] = per

    # --- provider level -------------------------------------------------------------------
    book = PeerBook.from_repo(repo)
    providers_raised: set[str] = set()
    providers_scored: set[str] = set()
    for pid in repo.provider_ids():
        res = provider_intensity(repo, pid, book)
        if res.metrics:
            providers_scored.add(pid)
        if res.findings:
            providers_raised.add(pid)

    # --- compare with the labels ----------------------------------------------------------
    scores: dict[str, TypeScore] = {}
    group_of_claim: dict[str, dict[str, str]] = defaultdict(dict)  # type -> claim -> group
    for atype in (*CLAIM_LEVEL, OUTLIER):
        scores[atype] = TypeScore(atype, "provider" if atype == OUTLIER else "claim")
    for _aid, atype, is_decoy, _provider, case_claims, case_lines in cases:
        group = "decoy" if is_decoy else "positive"
        if atype == OUTLIER:
            continue
        for cid in case_claims:
            group_of_claim[atype][cid] = group
        if atype in LINE_LEVEL and not is_decoy:
            sc = scores[atype]
            sc.line_cases += 1
            cited: set[str] = set()
            for cid in case_claims:
                for check in CLAIM_LEVEL[atype]:
                    cited |= raised.get(cid, {}).get(check, set())
            if case_lines and set(case_lines) <= cited:
                sc.line_cases_localised += 1
    group_sizes = {g: 0 for g in GROUPS}
    for atype, checks in CLAIM_LEVEL.items():
        sc = scores[atype]
        labels = group_of_claim[atype]
        sc.positives = sum(1 for g in labels.values() if g == "positive")
        sc.decoys = sum(1 for g in labels.values() if g == "decoy")
        sc.clean = len(claim_ids) - len(labels)
        for cid in claim_ids:
            hit = any(c in raised.get(cid, {}) for c in checks)
            group = labels.get(cid, "clean")
            if group == "positive":
                if hit:
                    sc.true_positives += 1
                else:
                    sc.missed.append(cid)
            elif hit and group == "decoy":
                sc.decoys_raised += 1
                sc.decoys_raised_ids.append(cid)
            elif hit:
                sc.clean_raised += 1
                sc.clean_raised_ids.append(cid)
    # the "any case" grouping for the near-match rates
    any_group: dict[str, str] = {}
    for labels in group_of_claim.values():
        for cid, g in labels.items():
            any_group[cid] = g
    for cid in claim_ids:
        group_sizes[any_group.get(cid, "clean")] += 1
    near_rates = {
        tier: {g: sum(1 for c in cids if any_group.get(c, "clean") == g) for g in GROUPS}
        for tier, cids in near.items()
    }
    for tier in (duplicates.NEAR_PROVIDER, duplicates.NEAR_DATE):
        near_rates.setdefault(tier, {g: 0 for g in GROUPS})

    out = scores[OUTLIER]
    outlier_labels = {
        p: ("decoy" if d else "positive") for _, t, d, p, _, _ in cases if t == OUTLIER and p
    }
    not_scored = {"positive": 0, "decoy": 0}
    out.positives = sum(1 for g in outlier_labels.values() if g == "positive")
    out.decoys = sum(1 for g in outlier_labels.values() if g == "decoy")
    out.clean = len(providers_scored - set(outlier_labels))
    for pid, group in sorted(outlier_labels.items()):
        if pid not in providers_scored:
            not_scored[group] += 1
            if group == "positive":
                out.missed.append(f"{pid} (not scored: too little data)")
    for pid in repo.provider_ids():
        if pid not in providers_scored:
            continue
        hit = pid in providers_raised
        group = outlier_labels.get(pid, "clean")
        if group == "positive":
            if hit:
                out.true_positives += 1
            else:
                out.missed.append(pid)
        elif hit and group == "decoy":
            out.decoys_raised += 1
            out.decoys_raised_ids.append(pid)
        elif hit:
            out.clean_raised += 1
            out.clean_raised_ids.append(pid)

    # checks with no label counterpart (code validation): how many claims raised them
    labelled = {c for checks in CLAIM_LEVEL.values() for c in checks}
    other: dict[str, int] = defaultdict(int)
    for per in raised.values():
        for check in per:
            if check not in labelled:
                other[check] += 1

    # does the tool confirm what each queue screen flagged?
    flag_rows = repo._con.execute("SELECT claim_id, screen_code FROM flag ORDER BY flag_id")
    triage: dict[str, dict[str, int]] = {}
    provider_of = {
        cid: pid for cid, pid in repo._con.execute("SELECT claim_id, provider_id FROM claim")
    }
    for cid, screen in flag_rows:
        atype = SCREEN_TYPE[screen]
        group = any_group.get(cid, "clean") if atype != OUTLIER else "n/a"
        if atype == OUTLIER:
            group = outlier_labels.get(provider_of[cid], "clean")
            hit = provider_of[cid] in providers_raised
        else:
            hit = any(c in raised.get(cid, {}) for c in CLAIM_LEVEL[atype])
        row = triage.setdefault(screen, defaultdict(int))
        row[f"flags_{group}"] += 1
        if hit:
            row[f"confirmed_{group}"] += 1

    params = parameters()
    return Scorecard(
        label=label,
        payer_hash=ph,
        params=params,
        params_hash=params_hash(params),
        icd_checked=icd is not None,
        claims_scored=len(claim_ids),
        types=scores,
        near_rates=near_rates,
        group_sizes=group_sizes,
        other_findings=dict(other),
        flag_triage={k: dict(v) for k, v in sorted(triage.items())},
        providers_not_scored=not_scored,
    )


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def render(card: Scorecard) -> str:
    lines = [
        f"# Tool scorecard: {card.label or 'unlabelled'}",
        "",
        f"payer sha256 {card.payer_hash[:16]}...  claims scored {card.claims_scored}  "
        f"params {card.params_hash}  full ICD list used: {card.icd_checked}",
        "",
        "| Parameter | Value |",
        "|---|---|",
        *(f"| {k} | {v} |" for k, v in card.params.items()),
        "",
        "| Type | Unit | Positives | Found | Recall | Raised | Precision | Decoys raised | "
        "Clean raised |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for t in card.types.values():
        lines.append(
            f"| {t.anomaly_type} | {t.level} | {t.positives} | {t.true_positives} | "
            f"{_pct(t.recall)} | {t.raised} | {_pct(t.precision)} | "
            f"{t.decoys_raised} of {t.decoys} | {t.clean_raised} of {t.clean} |"
        )
    lines += ["", "Line localisation (every labelled line cited by a finding):"]
    for atype in LINE_LEVEL:
        t = card.types[atype]
        lines.append(f"- {atype}: {t.line_cases_localised} of {t.line_cases} cases")
    lines += ["", "Missed positives and false alarms (ids):"]
    for t in card.types.values():
        lines.append(
            f"- {t.anomaly_type}: missed {t.missed or 'none'}; decoys raised "
            f"{t.decoys_raised_ids[:8] or 'none'}; clean raised {t.clean_raised_ids[:8] or 'none'}"
        )
    lines += ["", f"Providers with too little data to score: {card.providers_not_scored}"]
    lines += ["", "Near-match duplicate observations (claims, by label group):"]
    lines += [f"- {tier}: {rates}" for tier, rates in sorted(card.near_rates.items())]
    lines += [f"- group sizes: {card.group_sizes}"]
    lines += [
        "",
        f"Findings from checks with no labelled counterpart: {card.other_findings or 'none'}",
    ]
    lines += ["", "Queue screens (flags by label group; confirmed = the tool also raised it):"]
    lines += [f"- {screen}: {row}" for screen, row in card.flag_triage.items()]
    return "\n".join(lines) + "\n"


def _jsonable(card: Scorecard) -> dict[str, object]:
    data = json.loads(json.dumps(card, default=lambda o: o.__dict__))
    for name, t in card.types.items():
        data["types"][name]["precision"] = t.precision
        data["types"][name]["recall"] = t.recall
    return dict(data)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score the deterministic tools against the labels."
    )
    parser.add_argument("--data", type=Path, default=SYNTH_OUT_DIR)
    parser.add_argument("--label", default="")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)
    card = score_dataset(args.data, args.label)
    print(render(card))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(_jsonable(card), indent=2) + "\n")
        shown = (
            args.json.relative_to(REPO_ROOT) if args.json.is_relative_to(REPO_ROOT) else args.json
        )
        print(f"wrote {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
