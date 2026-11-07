"""Line-level independent evaluation (report only): do the tools cite the right claim lines?

An isolated author model (blind to this repository) delivers `claims.jsonl`, `rules.json` and
`labels.jsonl` using the brief in `eval/independent_lines/BRIEF_for_author.md`. Labels extend the
claim-level format with `case_kind`, `line_refs` (the exact lines that are the anomaly) and
`tempting_line_refs` (look-alike lines that are not). This module

1. validates the delivery with the existing claim-level validator (extension keys are split off
   first, nothing is repaired) plus line-reference checks,
2. loads it through `evals.independent.build_stores` unchanged,
3. runs the existing tools (`check_bundling`, `check_unit_limits`, `check_service_dates`) over every
   claim and compares the line ids they cite with the author's `line_refs`.

Only anomaly types that localise to lines are scored here (unbundling, excess units, date anomaly).
Whole-claim types such as duplicates and provider-level types are out of every denominator. This is
a report: it changes no tool and no threshold. Run:
`uv run python -m claims_copilot.evals.line_level --delivery DIR --json PATH`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claims_copilot.evals import independent as ind
from claims_copilot.evals.metrics import wilson_interval
from claims_copilot.project import REPO_ROOT
from claims_copilot.tools.edits import check_bundling, check_service_dates, check_unit_limits
from claims_copilot.tools.repository import Repository
from claims_copilot.tools.rules import SyntheticRules
from claims_copilot.tools.score import CLAIM_LEVEL

LINE_TYPES = ("unbundling", "excess_units", "date_anomaly")
KINDS = ("standard", "multi_line", "near_miss", "tempting_clean")
BASE_KEYS = {"case_id", "type", "label", "claim_ids", "provider_id", "reason"}
EXT_KEYS = {"case_kind", "line_refs", "tempting_line_refs"}
LINE_ID = re.compile(r"^(C\d{7})-L(\d+)$")
Ref = tuple[str, int]  # (author claim id, line number)


@dataclass(frozen=True)
class LineDelivery:
    delivery: ind.Delivery  # labels reduced to the six claim-level keys
    ext: dict[str, dict[str, Any]]  # case_id -> extension fields
    problems: list[str]


def load(directory: Path) -> LineDelivery:
    raw = ind.load_delivery(directory)
    base: list[dict[str, Any]] = []
    ext: dict[str, dict[str, Any]] = {}
    problems = list(raw.problems)
    for n, row in enumerate(raw.labels, start=1):
        keys = set(row)
        if keys != BASE_KEYS | EXT_KEYS:
            problems.append(f"labels.jsonl:{n}: wrong keys {sorted(keys ^ (BASE_KEYS | EXT_KEYS))}")
            continue
        base.append({k: row[k] for k in BASE_KEYS})
        ext[str(row["case_id"])] = {k: row[k] for k in EXT_KEYS}
    d = ind.Delivery(raw.claims, raw.rules, base, [])
    return LineDelivery(d, ext, problems)


def _refs(value: object) -> list[Ref] | None:
    if not isinstance(value, list):
        return None
    out: list[Ref] = []
    for r in value:
        if (
            not isinstance(r, dict)
            or set(r) != {"claim_id", "line_no"}
            or not isinstance(r["claim_id"], str)
            or not isinstance(r["line_no"], int)
            or isinstance(r["line_no"], bool)
        ):
            return None
        out.append((r["claim_id"], r["line_no"]))
    return out


@dataclass(frozen=True)
class Validation:
    schema_problems: list[str]
    requirement_gaps: list[str]


def validate(ld: LineDelivery) -> Validation:
    p = list(ld.problems)
    p += ind.validate(ld.delivery)
    lines_of: dict[str, set[int]] = {
        str(c.get("claim_id")): {
            ln["line_no"]
            for ln in c.get("lines", [])
            if isinstance(ln, dict) and isinstance(ln.get("line_no"), int)
        }
        for c in ld.delivery.claims
    }
    gaps: list[str] = []
    per_type: Counter[tuple[str, str]] = Counter()
    kinds: Counter[tuple[str, str, str]] = Counter()
    for row in ld.delivery.labels:
        cid = str(row["case_id"])
        e = ld.ext.get(cid)
        if e is None:
            continue
        typ, label = row["type"], row["label"]
        if typ not in (*LINE_TYPES, "clean"):
            p.append(f"{cid}: type {typ!r} is not line-level (only {LINE_TYPES} and clean)")
        if len(row["claim_ids"]) != 1:
            p.append(f"{cid}: one claim per case is required")
        if e["case_kind"] not in KINDS:
            p.append(f"{cid}: case_kind {e['case_kind']!r} not allowed")
        refs, tempt = _refs(e["line_refs"]), _refs(e["tempting_line_refs"])
        if refs is None or tempt is None:
            p.append(f"{cid}: line_refs and tempting_line_refs must be lists of claim_id/line_no")
            continue
        if (label == "TRUE") != bool(refs):
            p.append(f"{cid}: line_refs must be non-empty for TRUE and empty otherwise")
        for claim_id, line_no in (*refs, *tempt):
            if claim_id not in row["claim_ids"] or line_no not in lines_of.get(claim_id, set()):
                p.append(f"{cid}: reference {claim_id} line {line_no} is not a line of the case")
        if set(refs) & set(tempt):
            p.append(f"{cid}: a line cannot be both a reference line and a tempting line")
        per_type[(typ, label)] += 1
        kinds[(typ, label, e["case_kind"])] += 1
    for c in ld.delivery.claims:
        if len(c.get("lines", [])) < 2:
            p.append(f"claim {c.get('claim_id')}: needs at least two lines")
    missing = set(ld.ext) ^ {str(r["case_id"]) for r in ld.delivery.labels}
    p += [f"case {m}: extension fields missing or orphaned" for m in sorted(missing)]
    if not p:
        for typ in LINE_TYPES:
            if per_type[(typ, "TRUE")] < 12:
                gaps.append(f"{typ}: {per_type[(typ, 'TRUE')]} TRUE cases (brief asks for 12)")
            if kinds[(typ, "TRUE", "multi_line")] < 6:
                gaps.append(f"{typ}: fewer than 6 multi_line TRUE cases")
            if kinds[(typ, "DECOY", "near_miss")] < 8:
                gaps.append(f"{typ}: fewer than 8 near_miss decoys")
            if kinds[(typ, "DECOY", "tempting_clean")] < 6:
                gaps.append(f"{typ}: fewer than 6 tempting_clean decoys")
            two = sum(
                1
                for r in ld.delivery.labels
                if r["type"] == typ
                and r["label"] == "TRUE"
                and len(ld.ext[str(r["case_id"])]["line_refs"]) >= 2
            )
            if two < 3:
                gaps.append(f"{typ}: fewer than 3 TRUE cases with two anomalous lines")
        if per_type[("clean", "CLEAN")] < 30:
            gaps.append(f"{per_type[('clean', 'CLEAN')]} CLEAN claims (brief asks for 30)")
    return Validation(p, gaps)


# --- running the tools and scoring -----------------------------------------------------------


def cited_lines(repo: Repository, rules: SyntheticRules, claim_id: str) -> dict[str, set[int]]:
    """Check name -> line numbers it cites on this claim (repository ids)."""
    out: dict[str, set[int]] = defaultdict(set)
    for res in (
        check_bundling(repo, rules, claim_id),
        check_unit_limits(repo, rules, claim_id),
        check_service_dates(repo, claim_id),
    ):
        for f in res.findings:
            out[f.check]  # a finding with no line refs still counts as a flag
            for lid in f.ids("line"):
                m = LINE_ID.match(lid)
                if m and m.group(1) == claim_id:
                    out[f.check].add(int(m.group(2)))
    return dict(out)


def _rate(k: int, n: int) -> dict[str, Any]:
    if n == 0:
        return {"k": k, "n": n, "rate": None, "wilson95": None}
    w = wilson_interval(k, n)
    return {
        "k": k,
        "n": n,
        "rate": round(k / n, 4),
        "wilson95": [round(w.low, 4), round(w.high, 4)],
    }


def classify(expected: set[Ref], cited: set[Ref], flagged: bool) -> str:
    if cited == expected:
        return "exact"
    if not flagged:
        return "missed_claim"
    if not cited:
        return "flagged_without_line_refs"
    if not cited & expected:
        return "wrong_lines_only"
    if expected <= cited:
        return "over_cited"
    if cited < expected:
        return "missed_some_lines"
    return "missed_some_and_over_cited"


def score(ld: LineDelivery, repo: Repository, ids: ind.IdMap) -> dict[str, Any]:
    rules = SyntheticRules(repo)
    per_claim: dict[str, dict[str, set[int]]] = {}
    for author_id, repo_id in ids.claim.items():
        per_claim[author_id] = cited_lines(repo, rules, repo_id)
    in_case: set[str] = set()
    rows: list[dict[str, Any]] = []
    for lab in ld.delivery.labels:
        cid = str(lab["case_id"])
        e = ld.ext[cid]
        typ, label = lab["type"], lab["label"]
        claim = lab["claim_ids"][0]
        in_case.add(claim)
        expected = {(r["claim_id"], r["line_no"]) for r in e["line_refs"]}
        tempt = {(r["claim_id"], r["line_no"]) for r in e["tempting_line_refs"]}
        if typ == "clean":
            checks = {c for cs in CLAIM_LEVEL.values() for c in cs}
        else:
            checks = set(CLAIM_LEVEL[typ])
        mine = {k: v for k, v in per_claim[claim].items() if k in checks}
        cited = {(claim, n) for lines in mine.values() for n in lines}
        flagged = bool(mine)
        row: dict[str, Any] = {
            "case_id": cid,
            "type": typ,
            "label": label,
            "case_kind": e["case_kind"],
            "claim_id": claim,
            "expected_lines": sorted(n for _, n in expected),
            "tempting_lines": sorted(n for _, n in tempt),
            "cited_lines": sorted(n for _, n in cited),
            "claim_flagged": flagged,
        }
        if label == "TRUE":
            row["outcome"] = classify(expected, cited, flagged)
            row["tp_lines"] = len(expected & cited)
            row["extra_lines"] = sorted(n for _, n in cited - expected)
            row["extra_on_tempting_lines"] = sorted(n for _, n in (cited - expected) & tempt)
        else:
            row["outcome"] = "flagged" if flagged else "not_flagged"
            row["cited_on_tempting_lines"] = sorted(n for _, n in cited & tempt)
        rows.append(row)
    unlabelled = [c for c in per_claim if c not in in_case]
    stray = {c: per_claim[c] for c in unlabelled if per_claim[c]}

    def agg(sel: list[dict[str, Any]]) -> dict[str, Any]:
        true = [r for r in sel if r["label"] == "TRUE"]
        decoy = [r for r in sel if r["label"] == "DECOY"]
        expected = sum(len(r["expected_lines"]) for r in true)
        cited = sum(len(r["cited_lines"]) for r in true)
        tp = sum(r["tp_lines"] for r in true)
        over = sum(len(r["extra_lines"]) for r in true)
        return {
            "true_cases": len(true),
            "expected_lines": expected,
            "cited_lines_on_true_cases": cited,
            "line_recall": _rate(tp, expected),
            "line_precision": _rate(tp, cited),
            "claim_flag_rate_true": _rate(sum(1 for r in true if r["claim_flagged"]), len(true)),
            "exact_match_rate": _rate(sum(1 for r in true if r["outcome"] == "exact"), len(true)),
            "cases_with_over_citation": _rate(sum(1 for r in true if r["extra_lines"]), len(true)),
            "over_cited_lines": over,
            "over_cited_lines_on_tempting_lines": sum(
                len(r["extra_on_tempting_lines"]) for r in true
            ),
            "outcomes": dict(Counter(r["outcome"] for r in true)),
            "decoy_cases": len(decoy),
            "decoy_cases_with_cited_lines": _rate(
                sum(1 for r in decoy if r["cited_lines"]), len(decoy)
            ),
            "decoy_lines_cited": sum(len(r["cited_lines"]) for r in decoy),
            "decoy_lines_cited_on_tempting_lines": sum(
                len(r["cited_on_tempting_lines"]) for r in decoy
            ),
        }

    report: dict[str, Any] = {
        "cases": len(rows),
        "claims": len(per_claim),
        "by_type": {t: agg([r for r in rows if r["type"] == t]) for t in LINE_TYPES},
        "pooled": agg([r for r in rows if r["type"] in LINE_TYPES]),
        "by_case_kind": {
            k: agg([r for r in rows if r["type"] in LINE_TYPES and r["case_kind"] == k])
            for k in KINDS
        },
    }
    clean = [r for r in rows if r["type"] == "clean"]
    report["clean_claims"] = {
        "claims": len(clean) + len(unlabelled),
        "claims_with_cited_lines": sum(1 for r in clean if r["cited_lines"]) + len(stray),
        "lines_cited": sum(len(r["cited_lines"]) for r in clean)
        + sum(len(v) for per in stray.values() for v in per.values()),
        "labelled_clean_claims_raised": [r["case_id"] for r in clean if r["claim_flagged"]],
    }
    report["per_case"] = rows
    return report


def render(report: dict[str, Any]) -> str:
    lines = [f"cases {report['cases']}, claims {report['claims']}"]
    for name, a in (*report["by_type"].items(), ("POOLED", report["pooled"])):
        lines.append(
            f"{name}: TRUE {a['true_cases']} (expected lines {a['expected_lines']}); "
            f"line recall {a['line_recall']['k']}/{a['line_recall']['n']}, "
            f"line precision {a['line_precision']['k']}/{a['line_precision']['n']}, "
            f"exact {a['exact_match_rate']['k']}/{a['exact_match_rate']['n']}, "
            f"over-cited cases {a['cases_with_over_citation']['k']}, "
            f"decoy cases with cited lines {a['decoy_cases_with_cited_lines']['k']}"
            f"/{a['decoy_cases']}"
            f"; outcomes {a['outcomes']}"
        )
    c = report["clean_claims"]
    lines.append(
        f"clean claims {c['claims']}: with cited lines {c['claims_with_cited_lines']} "
        f"(lines {c['lines_cited']})"
    )
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Line-level evaluation of an independent delivery."
    )
    parser.add_argument(
        "--delivery", type=Path, default=REPO_ROOT / "eval" / "independent_lines" / "delivery"
    )
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "independent_lines")
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    ld = load(args.delivery)
    val = validate(ld)
    if val.schema_problems:
        print(f"INVALID: {len(val.schema_problems)} problem(s); nothing was loaded or repaired.")
        for line in val.schema_problems[:80]:
            print(f"- {line}")
        return 2
    print(f"valid: {len(ld.delivery.claims)} claims, {len(ld.delivery.labels)} cases")
    for gap in val.requirement_gaps:
        print(f"- gap: {gap}")
    if args.validate_only:
        return 0
    ids = ind.make_id_map(ld.delivery)
    ind.build_stores(ld.delivery, args.out, ids)
    repo = Repository.open(args.out / "payer.sqlite")
    report = score(ld, repo, ids)
    print(render(report))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        out = {
            "requirement_gaps": val.requirement_gaps,
            "files_sha256": {
                n: hashlib.sha256((args.delivery / n).read_bytes()).hexdigest()
                for n in ("claims.jsonl", "rules.json", "labels.jsonl")
                if (args.delivery / n).is_file()
            },
            **report,
        }
        args.json.write_text(json.dumps(out, indent=2) + "\n")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
