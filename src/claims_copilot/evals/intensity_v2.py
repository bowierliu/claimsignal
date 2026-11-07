"""Provider-intensity v1 versus v2 on a fresh independent fixture (pre-registered).

The pre-registration is `eval/provider_intensity_v2_preregistration.json`. The fixture is four files
written by an isolated author model from `eval/intensity_v2/BRIEF_for_author.md`:
`rules.json`, `providers.jsonl` (visit counts per level), `labels.jsonl` (sealed answers) and
`AUTHOR_NOTE.md`. This module validates them (reporting every problem, repairing nothing), loads
the counts into a temporary payer store as one single-line visit claim per count, runs the real
`provider_intensity` (v1, the control) and `provider_intensity_v2` over that store, and scores both
against the labels with the registered metrics and gates. It never edits the fixture and never
changes a constant.

Run: `uv run python -m claims_copilot.evals.intensity_v2 --fixture DIR --json PATH`
(temporary store goes to `data/intensity_v2/`, which is ignored).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claims_copilot.evals.metrics import wilson_interval
from claims_copilot.project import REPO_ROOT
from claims_copilot.synth.store import PAYER_FILE, PAYER_SCHEMA
from claims_copilot.tools import patterns_v2 as v2
from claims_copilot.tools.patterns import PeerBook, provider_intensity
from claims_copilot.tools.repository import Repository

FILES = ("rules.json", "providers.jsonl", "labels.jsonl", "AUTHOR_NOTE.md")
CODE_RE = re.compile(r"^X\d{4}$")
LABELS = ("TRUE", "DECOY", "ORDINARY")
STRATA = ("primary", "contamination")
SCORABLE_MIN_LINES = 40  # registered: the volume floor both versions share
PREREG_PATH = REPO_ROOT / "eval" / "provider_intensity_v2_preregistration.json"
LABEL_KEYS = {
    "provider_id",
    "specialty",
    "stratum",
    "label",
    "severity",
    "decoy_kind",
    "intended_high_share",
    "reason",
}
BANDS = (("<40", 0, 39), ("40-99", 40, 99), ("100-299", 100, 299), ("300+", 300, 10**9))


@dataclass(frozen=True)
class Fixture:
    visit_codes: list[str]
    providers: list[dict[str, Any]]
    labels: list[dict[str, Any]]
    hashes: dict[str, str]
    problems: list[str]


def _jsonl(path: Path, problems: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for n, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            problems.append(f"{path.name}:{n}: blank line")
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            problems.append(f"{path.name}:{n}: not valid JSON")
            continue
        if not isinstance(obj, dict):
            problems.append(f"{path.name}:{n}: not a JSON object")
            continue
        rows.append(obj)
    return rows


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_fixture(directory: Path) -> Fixture:
    problems: list[str] = []
    missing = [n for n in FILES if not (directory / n).is_file()]
    if missing:
        return Fixture([], [], [], {}, [f"missing file: {n}" for n in missing])
    hashes = {n: sha256_file(directory / n) for n in FILES}
    visit_codes: list[str] = []
    try:
        rules = json.loads((directory / "rules.json").read_text())
        codes = rules.get("visit_codes") if isinstance(rules, dict) else None
        if isinstance(codes, list):
            visit_codes = [str(c) for c in codes]
        else:
            problems.append("rules.json: visit_codes must be a list")
    except json.JSONDecodeError:
        problems.append("rules.json: not valid JSON")
    providers = _jsonl(directory / "providers.jsonl", problems)
    labels = _jsonl(directory / "labels.jsonl", problems)
    return Fixture(visit_codes, providers, labels, hashes, problems)


def lines_of(provider: dict[str, Any]) -> int:
    return sum(int(v) for v in provider["visit_counts"].values())


def high_lines_of(provider: dict[str, Any], visit_codes: list[str]) -> int:
    return int(provider["visit_counts"][visit_codes[-1]])


@dataclass(frozen=True)
class Validation:
    schema_problems: list[str]  # block scoring
    requirement_gaps: list[str]  # brief requirements not met: recorded, scoring proceeds


def validate(fx: Fixture) -> Validation:
    p = list(fx.problems)
    gaps: list[str] = []
    codes = fx.visit_codes
    if len(codes) < 4 or len(set(codes)) != len(codes) or any(not CODE_RE.match(c) for c in codes):
        p.append("rules.json: need at least four distinct visit codes, each X plus four digits")
    ids = Counter(str(r.get("provider_id")) for r in fx.providers)
    p += [f"providers.jsonl: duplicate provider id {k}" for k, v in ids.items() if v > 1]
    by_id: dict[str, dict[str, Any]] = {}
    for n, r in enumerate(fx.providers, start=1):
        where = f"providers.jsonl:{n}"
        if set(r) != {"provider_id", "specialty", "visit_counts"}:
            p.append(f"{where}: wrong keys")
            continue
        if not isinstance(r["provider_id"], str) or not r["provider_id"]:
            p.append(f"{where}: provider_id must be a non-empty string")
            continue
        if not isinstance(r["specialty"], str) or not r["specialty"]:
            p.append(f"{where}: specialty must be a non-empty string")
            continue
        vc = r["visit_counts"]
        if not isinstance(vc, dict) or set(vc) != set(codes):
            p.append(f"{where}: visit_counts must have exactly the rules.json visit codes")
            continue
        if any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in vc.values()):
            p.append(f"{where}: counts must be non-negative integers")
            continue
        by_id[r["provider_id"]] = r
    label_by_id: dict[str, dict[str, Any]] = {}
    for n, r in enumerate(fx.labels, start=1):
        where = f"labels.jsonl:{n}"
        if set(r) != LABEL_KEYS:
            p.append(f"{where}: wrong keys")
            continue
        pid = r["provider_id"]
        if pid in label_by_id:
            p.append(f"{where}: duplicate label for {pid}")
            continue
        label_by_id[str(pid)] = r
        if r["label"] not in LABELS:
            p.append(f"{where}: label {r['label']!r} not allowed")
        if r["stratum"] not in STRATA:
            p.append(f"{where}: stratum {r['stratum']!r} not allowed")
        if (r["severity"] is not None) != (r["label"] == "TRUE") or (
            r["severity"] is not None and r["severity"] not in ("mild", "strong")
        ):
            p.append(f"{where}: severity must be mild/strong for TRUE and null otherwise")
        if (r["decoy_kind"] is not None) != (r["label"] == "DECOY") or (
            r["decoy_kind"] is not None and r["decoy_kind"] not in ("hard", "easy")
        ):
            p.append(f"{where}: decoy_kind must be hard/easy for DECOY and null otherwise")
        share = r["intended_high_share"]
        if not isinstance(share, (int, float)) or isinstance(share, bool) or not 0 <= share <= 1:
            p.append(f"{where}: intended_high_share must be between 0 and 1")
        if not isinstance(r["reason"], str) or not r["reason"].strip():
            p.append(f"{where}: empty reason")
        if pid in by_id and by_id[pid]["specialty"] != r["specialty"]:
            p.append(f"{where}: specialty differs from providers.jsonl for {pid}")
    p += [f"provider {k} has no label" for k in sorted(set(by_id) - set(label_by_id))]
    p += [f"label for unknown provider {k}" for k in sorted(set(label_by_id) - set(by_id))]
    if p:
        return Validation(p, gaps)

    # Brief requirements (recorded as gaps; nothing is repaired).
    spec_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for lab in label_by_id.values():
        spec_rows[lab["specialty"]].append(lab)
    primary = sorted({s for s, rows in spec_rows.items() if rows[0]["stratum"] == "primary"})
    contamination = sorted(
        {s for s, rows in spec_rows.items() if rows[0]["stratum"] == "contamination"}
    )
    for s, rows in spec_rows.items():
        if len({r["stratum"] for r in rows}) != 1:
            gaps.append(f"{s}: providers carry more than one stratum")
    if len(primary) < 3:
        gaps.append(f"need at least 3 primary specialties, found {len(primary)}")
    if len(contamination) < 1:
        gaps.append("no contamination stratum declared")
    for s in primary:
        rows = spec_rows[s]
        n = len(rows)
        cnt = Counter(r["label"] for r in rows)
        if cnt["ORDINARY"] < 30:
            gaps.append(f"{s}: {cnt['ORDINARY']} ordinary providers (need at least 30)")
        if cnt["TRUE"] < 3 or cnt["TRUE"] / n > 0.15:
            gaps.append(f"{s}: TRUE {cnt['TRUE']} of {n} (need 3 or more and at most 15%)")
        if cnt["DECOY"] < 3 or cnt["DECOY"] / n > 0.15:
            gaps.append(f"{s}: DECOY {cnt['DECOY']} of {n} (need 3 or more and at most 15%)")
        sev = Counter(r["severity"] for r in rows if r["label"] == "TRUE")
        if sev["mild"] < 3 or sev["strong"] < 3:
            gaps.append(f"{s}: TRUE severities {dict(sev)} (need 3 mild and 3 strong)")
        if sum(1 for r in rows if r["decoy_kind"] == "hard") < 3:
            gaps.append(f"{s}: fewer than 3 hard decoys")
        vol = {r["provider_id"]: lines_of(by_id[r["provider_id"]]) for r in rows}
        low = [pid for pid, v in vol.items() if v <= 30]
        mid = [pid for pid, v in vol.items() if 31 <= v <= 70]
        if len(low) < 6 or len(mid) < 8:
            gaps.append(f"{s}: {len(low)} providers at 30 or fewer lines, {len(mid)} at 31-70")
        for lab_name in ("TRUE", "DECOY"):
            if not any(label_by_id[pid]["label"] == lab_name for pid in low):
                gaps.append(f"{s}: no low-volume {lab_name} provider")
    for s in contamination:
        rows = spec_rows[s]
        cnt = Counter(r["label"] for r in rows)
        share = cnt["TRUE"] / len(rows)
        if cnt["ORDINARY"] < 30:
            gaps.append(f"{s}: {cnt['ORDINARY']} ordinary providers (need at least 30)")
        if not 0.30 <= share <= 0.45:
            gaps.append(f"{s}: TRUE share {share:.2f} outside 0.30 to 0.45")
    return Validation(p, gaps)


# --- repository ----------------------------------------------------------------------------------


def provider_id_map(fx: Fixture) -> dict[str, str]:
    """Author provider id -> repository id (`P0001`, ...), in file order. Only the id changes."""
    return {str(r["provider_id"]): f"P{i + 1:04d}" for i, r in enumerate(fx.providers)}


def build_repository(fx: Fixture, out_dir: Path, ids: dict[str, str]) -> Repository:
    """One single-line visit claim per count. No labels are stored."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / PAYER_FILE
    path.unlink(missing_ok=True)  # our own temporary output
    con = sqlite3.connect(path)
    con.executescript(PAYER_SCHEMA)
    with con:
        con.execute("INSERT INTO meta VALUES ('payer_hash', 'intensity-v2-fixture')")
        con.execute("INSERT INTO member VALUES ('M000001', '40-49', 'F', 'PPO', 'R1')")
        con.executemany(
            "INSERT INTO procedure_code VALUES (?,?,?,?,?,?)",
            [(c, "fixture", "VISIT", "VISIT", i + 1, "0.00") for i, c in enumerate(fx.visit_codes)],
        )
        con.executemany(
            "INSERT INTO provider VALUES (?,?,?,?)",
            [(ids[r["provider_id"]], r["specialty"], "R1", "G1") for r in fx.providers],
        )
        claim_rows: list[tuple[str, ...]] = []
        line_rows: list[tuple[object, ...]] = []
        n = 0
        for r in fx.providers:
            pid = ids[r["provider_id"]]
            for code in fx.visit_codes:
                for _ in range(int(r["visit_counts"][code])):
                    n += 1
                    cid = f"C{n:07d}"
                    claim_rows.append(
                        (cid, "M000001", pid, "2026-11-03", "2026-11-03", "PS1", "1.00")
                    )
                    line_rows.append((f"{cid}-L1", cid, 1, code, 1, "1.00", "2026-11-03", 1))
        con.executemany("INSERT INTO claim VALUES (?,?,?,?,?,?,?)", claim_rows)
        con.executemany("INSERT INTO claim_line VALUES (?,?,?,?,?,?,?,?)", line_rows)
    con.close()
    return Repository.open(path)


# --- scoring -------------------------------------------------------------------------------------


def _v1_outcome(repo: Repository, pid: str, book: PeerBook) -> dict[str, Any]:
    res = provider_intensity(repo, pid, book)
    metrics = dict(res.metrics)
    if not metrics:
        reason = (
            "below_min_volume" if any("visit lines" in s for s in res.limits) else "too_few_peers"
        )
        return {"outcome": "abstain", "reason": reason}
    return {
        "outcome": "flag" if res.findings else "no_flag",
        "reason": None,
        "score": float(metrics["score"]),
    }


def _v2_outcome(repo: Repository, pid: str, book: PeerBook) -> dict[str, Any]:
    res = v2.provider_intensity_v2(repo, pid, book)
    metrics = dict(res.metrics)
    decision = metrics["decision"]
    if decision == "abstain":
        return {"outcome": "abstain", "reason": metrics["abstention_reason"]}
    return {
        "outcome": decision,
        "reason": None,
        "p_value": float(metrics["p_value"]),
        "gap_above_p75": float(metrics["gap_above_p75"]),
    }


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


def score_fixture(fx: Fixture, repo: Repository, ids: dict[str, str]) -> dict[str, Any]:
    labels = {str(r["provider_id"]): r for r in fx.labels}
    provs = {str(r["provider_id"]): r for r in fx.providers}
    book = PeerBook.from_repo(repo)
    rows: list[dict[str, Any]] = []
    for pid, prov in provs.items():
        lab = labels[pid]
        n = lines_of(prov)
        high = high_lines_of(prov, fx.visit_codes)
        rows.append(
            {
                "provider_id": pid,
                "specialty": lab["specialty"],
                "stratum": lab["stratum"],
                "label": lab["label"],
                "severity": lab["severity"],
                "decoy_kind": lab["decoy_kind"],
                "intended_high_share": lab["intended_high_share"],
                "visit_lines": n,
                "high_share": round(high / n, 4) if n else 0.0,
                "scorable": n >= SCORABLE_MIN_LINES,
                "v1": _v1_outcome(repo, ids[pid], book),
                "v2": _v2_outcome(repo, ids[pid], book),
            }
        )

    def tally(sel: list[dict[str, Any]], version: str) -> dict[str, Any]:
        flagged = sum(1 for r in sel if r[version]["outcome"] == "flag")
        abst = Counter(r[version]["reason"] for r in sel if r[version]["outcome"] == "abstain")
        return {**_rate(flagged, len(sel)), "abstentions": dict(abst)}

    def pick(**kw: Any) -> list[dict[str, Any]]:
        out = rows
        for key, val in kw.items():
            if key == "labels":
                out = [r for r in out if r["label"] in val]
            elif key == "scorable":
                out = [r for r in out if r["scorable"] == val]
            else:
                out = [r for r in out if r[key] == val]
        return out

    primary = pick(stratum="primary")
    report: dict[str, Any] = {"providers": len(rows)}
    versions = ("v1", "v2")
    prim: dict[str, Any] = {}
    for v in versions:
        true_sel = [r for r in primary if r["label"] == "TRUE" and r["scorable"]]
        neg_sel = [r for r in primary if r["label"] != "TRUE" and r["scorable"]]
        prim[v] = {
            "recall": tally(true_sel, v),
            "false_positive_rate": tally(neg_sel, v),
            "false_alarm_count": sum(1 for r in neg_sel if r[v]["outcome"] == "flag"),
        }
    report["primary"] = prim

    sec: dict[str, Any] = {}
    for v in versions:
        s: dict[str, Any] = {}
        by_spec: dict[str, Any] = {}
        for spec in sorted({r["specialty"] for r in primary}):
            sp = [r for r in primary if r["specialty"] == spec and r["scorable"]]
            by_spec[spec] = {
                "recall": tally([r for r in sp if r["label"] == "TRUE"], v),
                "false_positive_rate": tally([r for r in sp if r["label"] != "TRUE"], v),
            }
        s["by_specialty"] = by_spec
        s["recall_by_severity"] = {
            sev: tally(
                [
                    r
                    for r in primary
                    if r["label"] == "TRUE" and r["scorable"] and r["severity"] == sev
                ],
                v,
            )
            for sev in ("mild", "strong")
        }
        s["recall_by_volume_band"] = {
            name: tally(
                [r for r in primary if r["label"] == "TRUE" and lo <= r["visit_lines"] <= hi], v
            )
            for name, lo, hi in BANDS
        }
        s["fpr_ordinary_only"] = tally(
            [r for r in primary if r["label"] == "ORDINARY" and r["scorable"]], v
        )
        s["fpr_decoy_only"] = tally(
            [r for r in primary if r["label"] == "DECOY" and r["scorable"]], v
        )
        s["fpr_hard_decoy_only"] = tally(
            [r for r in primary if r["decoy_kind"] == "hard" and r["scorable"]], v
        )
        s["recall_all_true_including_below_floor"] = tally(
            [r for r in primary if r["label"] == "TRUE"], v
        )
        s["abstentions_by_label"] = {
            lab: dict(
                Counter(
                    r[v]["reason"]
                    for r in primary
                    if r["label"] == lab and r[v]["outcome"] == "abstain"
                )
            )
            for lab in LABELS
        }
        contam = [r for r in rows if r["stratum"] == "contamination"]
        s["contamination_stratum_sensitivity_not_in_gate"] = {
            "recall_scorable_true": tally(
                [r for r in contam if r["label"] == "TRUE" and r["scorable"]], v
            ),
            "false_positive_rate_scorable_ordinary_and_decoy": tally(
                [r for r in contam if r["label"] != "TRUE" and r["scorable"]], v
            ),
            "abstentions_all_providers": dict(
                Counter(r[v]["reason"] for r in contam if r[v]["outcome"] == "abstain")
            ),
        }
        sec[v] = s
    report["secondary"] = sec
    report["per_provider"] = rows
    return report


def evaluate_gates(report: dict[str, Any], prereg: dict[str, Any]) -> dict[str, Any]:
    gates = prereg["acceptance_gates"]
    p1, p2 = report["primary"]["v1"], report["primary"]["v2"]
    r1, r2 = p1["recall"]["rate"], p2["recall"]["rate"]
    f2 = p2["false_positive_rate"]["rate"]
    out: dict[str, Any] = {
        "G1_v2_recall": {
            "value": r2,
            "required": f">= {gates['G1_v2_recall_min']}",
            "passed": r2 is not None and r2 >= gates["G1_v2_recall_min"],
        },
        "G2_improvement_over_v1": {
            "value": None if r1 is None or r2 is None else round(r2 - r1, 4),
            "v1_recall": r1,
            "required": f">= {gates['G2_v2_recall_improvement_over_v1_min']}",
            "passed": r1 is not None
            and r2 is not None
            and round(r2 - r1, 10) >= gates["G2_v2_recall_improvement_over_v1_min"],
        },
        "G3_v2_false_positive_rate": {
            "value": f2,
            "required": f"<= {gates['G3_v2_false_positive_rate_max']}",
            "passed": f2 is not None and f2 <= gates["G3_v2_false_positive_rate_max"],
        },
        "G4_false_alarms_not_more_than_v1": {
            "v2": p2["false_alarm_count"],
            "v1": p1["false_alarm_count"],
            "required": "v2 <= v1",
            "passed": p2["false_alarm_count"] <= p1["false_alarm_count"],
        },
    }
    out["all_passed"] = all(g["passed"] for g in out.values() if isinstance(g, dict))
    out["decision"] = (
        "v2 meets every registered gate; it remains experimental until the owner decides"
        if out["all_passed"]
        else "v2 failed at least one registered gate: it stays experimental, v1 stays the "
        "product default, and the miss is recorded without tuning"
    )
    return out


def render(report: dict[str, Any], gates: dict[str, Any]) -> str:
    lines = [f"providers scored: {report['providers']}"]
    for v in ("v1", "v2"):
        p = report["primary"][v]
        r, f = p["recall"], p["false_positive_rate"]
        lines.append(
            f"{v}: recall {r['k']}/{r['n']} (Wilson {r['wilson95']}), false positives "
            f"{f['k']}/{f['n']} (Wilson {f['wilson95']}); abstentions on scorable "
            f"TRUE {r['abstentions']}, on scorable negatives {f['abstentions']}"
        )
    for name, g in gates.items():
        if isinstance(g, dict):
            lines.append(f"{name}: {'PASS' if g['passed'] else 'FAIL'} {g}")
    lines.append(gates["decision"])
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score provider-intensity v1 and v2 on a fixture.")
    parser.add_argument(
        "--fixture", type=Path, default=REPO_ROOT / "eval" / "intensity_v2" / "fixture"
    )
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "intensity_v2")
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    fx = load_fixture(args.fixture)
    val = validate(fx)
    print("fixture sha256:", json.dumps(fx.hashes))
    if val.schema_problems:
        print(
            f"INVALID: {len(val.schema_problems)} schema problem(s); nothing was loaded "
            "or repaired."
        )
        for line in val.schema_problems[:60]:
            print(f"- {line}")
        return 2
    print(f"valid: {len(fx.providers)} providers; {len(val.requirement_gaps)} requirement gap(s)")
    for gap in val.requirement_gaps:
        print(f"- gap: {gap}")
    if args.validate_only:
        return 0
    prereg = json.loads(PREREG_PATH.read_text())
    ids = provider_id_map(fx)
    repo = build_repository(fx, args.out, ids)
    report = score_fixture(fx, repo, ids)
    gates = evaluate_gates(report, prereg)
    print(render(report, gates))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        out = {
            "preregistration_sha256": sha256_file(PREREG_PATH),
            "fixture_sha256": fx.hashes,
            "requirement_gaps": val.requirement_gaps,
            "v2_constants": prereg["v2"]["constants"],
            "gates": gates,
            **report,
        }
        args.json.write_text(json.dumps(out, indent=2) + "\n")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
