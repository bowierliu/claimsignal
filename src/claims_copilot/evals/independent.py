"""Independent-author tool test: validate a delivery, build a temporary dataset, score it.

An outside author (another model, blind to this repository) delivers `claims.jsonl`, `rules.json`
and `labels.jsonl` from public rules. This module never edits them. It

1. validates them and reports every problem (nothing is repaired),
2. loads the claims and the author's own rules into a temporary payer store with the existing
   schema, and the labels into a separate label store in the same layout `tools.score` reads, and
3. calls `tools.score.score_dataset` unchanged, so the scoring logic is the one used for the
   generator-made data. Line localisation is not measured (the author labelled claims, not lines).

Labels are never placed in the payer store. Run (defaults are the paths below):
`uv run python -m claims_copilot.evals.independent --json PATH`
with the delivery in `eval/independent/` and temporary output in `data/independent/` (ignored).
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sqlite3
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from claims_copilot.evals.metrics import wilson_interval
from claims_copilot.project import REPO_ROOT
from claims_copilot.synth.store import PAYER_FILE, PAYER_SCHEMA, TRUTH_FILE, TRUTH_SCHEMA
from claims_copilot.tools.icd import IcdSourceUnavailableError, load_icd_codes
from claims_copilot.tools.score import Scorecard, render, score_dataset

TYPES = ("duplicate_claim", "unbundling", "excess_units", "intensity_outlier", "date_anomaly")
LABELS = ("TRUE", "DECOY", "CLEAN")
CODE_RE = re.compile(r"^X\d{4}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONEY_RE = re.compile(r"^\d+\.\d{2}$")
WINDOW = (date(2026, 10, 1), date(2027, 9, 30))
POS = ("PS1", "PS2", "PS3")
MODIFIERS = ("M1", "M2", "M3")
MEMBER_KEYS = ("member_id", "age_band", "sex", "plan_type", "region")
PROVIDER_KEYS = ("provider_id", "specialty", "region", "group_id")
LINE_KEYS = {"line_no", "code", "units", "billed_amount", "service_date", "modifiers", "dx_pointer"}
CLAIM_KEYS = {
    "claim_id",
    "member",
    "provider",
    "service_from",
    "service_to",
    "place_of_service",
    "total_billed",
    "diagnoses",
    "lines",
}
# Anything that reads like a person, address or free-text description in a field that should hold
# only a coded value is reported (not repaired).
SUSPECT_TEXT = re.compile(r"[a-z]{4,}\s+[a-z]{3,}", re.IGNORECASE)


@dataclass
class Delivery:
    claims: list[dict[str, Any]]
    rules: dict[str, Any]
    labels: list[dict[str, Any]]
    problems: list[str] = field(default_factory=list)


def _read_jsonl(path: Path, problems: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    text = gzip.decompress(path.read_bytes()).decode() if path.suffix == ".gz" else path.read_text()
    for n, line in enumerate(text.splitlines(), start=1):
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


def _iso(value: object) -> date | None:
    if not isinstance(value, str) or not DATE_RE.match(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _money(value: object) -> Decimal | None:
    if not isinstance(value, str) or not MONEY_RE.match(value):
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def load_delivery(directory: Path) -> Delivery:
    problems: list[str] = []
    # The claims file is committed gzip-compressed (the repository's large-file hook); the
    # uncompressed original is accepted too and has the same sha256 once decompressed.
    claims_path = next(
        (p for p in (directory / "claims.jsonl", directory / "claims.jsonl.gz") if p.is_file()),
        directory / "claims.jsonl",
    )
    missing = [n for n in ("rules.json", "labels.jsonl") if not (directory / n).is_file()]
    if not claims_path.is_file():
        missing.insert(0, "claims.jsonl")
    if missing:
        return Delivery([], {}, [], [f"missing file: {n}" for n in missing])
    claims = _read_jsonl(claims_path, problems)
    labels = _read_jsonl(directory / "labels.jsonl", problems)
    try:
        rules = json.loads((directory / "rules.json").read_text())
    except json.JSONDecodeError:
        rules = {}
        problems.append("rules.json: not valid JSON")
    return Delivery(claims, rules if isinstance(rules, dict) else {}, labels, problems)


def validate(d: Delivery) -> list[str]:
    """Every problem found. An empty list means the delivery may be loaded."""
    p = list(d.problems)
    rules = d.rules
    visit = rules.get("visit_codes", [])
    other = rules.get("procedure_codes", [])
    bundles = rules.get("bundle_pairs", [])
    limits = rules.get("unit_limits", [])
    if not (isinstance(visit, list) and len(visit) >= 3):
        p.append("rules.json: visit_codes needs at least three codes")
    if not isinstance(other, list):
        p.append("rules.json: procedure_codes must be a list")
    declared = set(visit if isinstance(visit, list) else []) | set(
        other if isinstance(other, list) else []
    )
    for c in sorted(declared):
        if not isinstance(c, str) or not CODE_RE.match(c):
            p.append(f"rules.json: code {c!r} is not X plus four digits")
    if len(bundles) < 5 or len(limits) < 5:
        p.append("rules.json: needs at least five bundle pairs and five unit limits")
    for b in bundles:
        if not isinstance(b, dict) or set(b) != {
            "comprehensive_code",
            "component_code",
            "exception_modifier",
        }:
            p.append(f"rules.json: bad bundle pair {b!r}")
            continue
        for k in ("comprehensive_code", "component_code"):
            if b[k] not in declared:
                p.append(f"rules.json: bundle code {b[k]!r} not declared")
        if b["exception_modifier"] not in MODIFIERS:
            p.append(f"rules.json: exception modifier {b['exception_modifier']!r} not allowed")
    for u in limits:
        if not isinstance(u, dict) or set(u) != {"code", "max_units"}:
            p.append(f"rules.json: bad unit limit {u!r}")
            continue
        if u["code"] not in declared:
            p.append(f"rules.json: limit code {u['code']!r} not declared")
        if not isinstance(u["max_units"], int) or u["max_units"] < 1:
            p.append(f"rules.json: bad max_units for {u['code']!r}")

    try:
        icd = load_icd_codes()
    except IcdSourceUnavailableError:
        icd = None
        p.append("cannot check diagnosis codes: the local FY2027 ICD-10-CM file is unavailable")

    ids: Counter[str] = Counter()
    members: dict[str, dict[str, Any]] = {}
    providers: dict[str, dict[str, Any]] = {}
    for n, c in enumerate(d.claims, start=1):
        cid = str(c.get("claim_id"))
        where = f"claims.jsonl:{n} ({cid})"
        ids[cid] += 1
        if set(c) != CLAIM_KEYS:
            p.append(f"{where}: unexpected or missing keys {sorted(set(c) ^ CLAIM_KEYS)}")
            continue
        for who, keys, seen in (
            ("member", MEMBER_KEYS, members),
            ("provider", PROVIDER_KEYS, providers),
        ):
            ent = c[who]
            if not isinstance(ent, dict) or set(ent) != set(keys):
                p.append(f"{where}: {who} has wrong keys")
                continue
            if any(not isinstance(ent[k], str) or not ent[k] for k in keys):
                p.append(f"{where}: {who} has an empty or non-string field")
                continue
            prior = seen.setdefault(ent[keys[0]], ent)
            if prior != ent:
                p.append(f"{where}: {who} {ent[keys[0]]} differs from an earlier claim")
        f, t = _iso(c["service_from"]), _iso(c["service_to"])
        if f is None or t is None:
            p.append(f"{where}: bad service dates")
        elif t < f:
            p.append(f"{where}: service_to before service_from")
        if c["place_of_service"] not in POS:
            p.append(f"{where}: place_of_service not in {POS}")
        total = _money(c["total_billed"])
        if total is None:
            p.append(f"{where}: bad total_billed")
        dx = c["diagnoses"]
        if not isinstance(dx, list) or not dx:
            p.append(f"{where}: diagnoses must be a non-empty list")
            dx = []
        for code in dx:
            if icd is not None and not (isinstance(code, str) and icd.contains(code)):
                p.append(f"{where}: diagnosis {code!r} not in the FY2027 ICD-10-CM list")
        lines = c["lines"]
        if not isinstance(lines, list) or not lines:
            p.append(f"{where}: lines must be a non-empty list")
            continue
        running = Decimal(0)
        for i, ln in enumerate(lines, start=1):
            if not isinstance(ln, dict) or set(ln) != LINE_KEYS:
                p.append(f"{where}: line {i} has wrong keys")
                continue
            if ln["line_no"] != i:
                p.append(f"{where}: line numbers are not 1, 2, 3 ...")
            if ln["code"] not in declared:
                p.append(f"{where}: line {i} code {ln['code']!r} not declared in rules.json")
            if not isinstance(ln["units"], int) or isinstance(ln["units"], bool) or ln["units"] < 1:
                p.append(f"{where}: line {i} units must be an integer of at least 1")
            amt = _money(ln["billed_amount"])
            if amt is None:
                p.append(f"{where}: line {i} bad billed_amount")
            else:
                running += amt
            if _iso(ln["service_date"]) is None:
                p.append(f"{where}: line {i} bad service_date")
            else:
                day = _iso(ln["service_date"])
                if day is not None and not WINDOW[0] <= day <= WINDOW[1]:
                    p.append(f"{where}: line {i} date outside the FY2027 window")
            mods = ln["modifiers"]
            if not isinstance(mods, list) or any(m not in MODIFIERS for m in mods):
                p.append(f"{where}: line {i} bad modifiers")
            ptr = ln["dx_pointer"]
            if not isinstance(ptr, int) or not 1 <= ptr <= max(len(dx), 1):
                p.append(f"{where}: line {i} dx_pointer out of range")
        if total is not None and running != total:
            p.append(f"{where}: total_billed {total} != sum of lines {running}")
        for who in ("member", "provider"):
            ent = c[who]
            if isinstance(ent, dict):
                for v in ent.values():
                    if isinstance(v, str) and SUSPECT_TEXT.search(v):
                        p.append(f"{where}: {who} field {v!r} looks like free text")
    p += [f"duplicate claim id {k} ({v} rows)" for k, v in ids.items() if v > 1]
    claim_ids = set(ids)

    # --- labels ---------------------------------------------------------------------------
    case_ids: Counter[str] = Counter()
    claim_case: dict[str, list[str]] = {}
    intensity_providers: dict[str, str] = {}
    claim_provider = {
        str(c.get("claim_id")): c["provider"]["provider_id"]
        for c in d.claims
        if isinstance(c.get("provider"), dict) and "provider_id" in c["provider"]
    }
    for n, row in enumerate(d.labels, start=1):
        where = f"labels.jsonl:{n}"
        if set(row) != {"case_id", "type", "label", "claim_ids", "provider_id", "reason"}:
            p.append(f"{where}: wrong keys")
            continue
        case_ids[str(row["case_id"])] += 1
        typ, label = row["type"], row["label"]
        if label not in LABELS:
            p.append(f"{where}: label {label!r} not allowed")
        if typ not in (*TYPES, "clean"):
            p.append(f"{where}: type {typ!r} not allowed")
        if (label == "CLEAN") != (typ == "clean"):
            p.append(f"{where}: CLEAN and type clean must go together")
        if not isinstance(row["reason"], str) or not row["reason"].strip():
            p.append(f"{where}: empty reason")
        cl = row["claim_ids"]
        if typ == "intensity_outlier":
            pid = row["provider_id"]
            if cl != [] or not isinstance(pid, str):
                p.append(f"{where}: intensity cases need provider_id and an empty claim_ids")
            elif pid not in set(claim_provider.values()):
                p.append(f"{where}: provider {pid} has no claims")
            else:
                intensity_providers[pid] = label
        else:
            if not isinstance(cl, list) or not cl or row["provider_id"] is not None:
                p.append(f"{where}: needs claim_ids and a null provider_id")
                continue
            for cid in cl:
                if cid not in claim_ids:
                    p.append(f"{where}: claim {cid} not in claims.jsonl")
                claim_case.setdefault(cid, []).append(str(row["case_id"]))
    p += [f"duplicate case id {k}" for k, v in case_ids.items() if v > 1]
    p += [f"claim {k} is in several cases {v}" for k, v in claim_case.items() if len(v) > 1]

    labelled_providers = {claim_provider[c] for c in claim_case if c in claim_provider}
    overlap = labelled_providers & set(intensity_providers)
    if overlap:
        p.append(f"providers in both a claim-level case and an intensity case: {sorted(overlap)}")
    for c in sorted(claim_ids - set(claim_case)):
        prov = claim_provider.get(c)
        if prov in intensity_providers:
            continue
        # background providers: every claim of theirs must be unlabelled
        if prov in labelled_providers:
            p.append(f"claim {c} has no case but its provider appears in a claim-level case")
    return p


@dataclass(frozen=True)
class IdMap:
    """Author id -> repository id. Our tools accept only their own id shapes (`C0000001`,
    `M000001`, `P0001`), so ids are renamed mechanically in order of first appearance. Nothing
    else about a row changes. The map is saved next to the temporary stores."""

    claim: dict[str, str]
    member: dict[str, str]
    provider: dict[str, str]

    def reverse(self) -> dict[str, str]:
        return {v: k for m in (self.claim, self.member, self.provider) for k, v in m.items()}


def make_id_map(d: Delivery) -> IdMap:
    claim: dict[str, str] = {}
    member: dict[str, str] = {}
    provider: dict[str, str] = {}
    for c in d.claims:
        claim.setdefault(c["claim_id"], f"C{len(claim) + 1:07d}")
        member.setdefault(c["member"]["member_id"], f"M{len(member) + 1:06d}")
        provider.setdefault(c["provider"]["provider_id"], f"P{len(provider) + 1:04d}")
    return IdMap(claim, member, provider)


def build_stores(d: Delivery, out_dir: Path, ids: IdMap) -> None:
    """Write `payer.sqlite` (claims and the author's rules only) and the label store."""
    out_dir.mkdir(parents=True, exist_ok=True)
    payer, labels_db = out_dir / PAYER_FILE, out_dir / TRUTH_FILE
    for path in (payer, labels_db):
        path.unlink(missing_ok=True)  # our own temporary output
    visit = list(d.rules["visit_codes"])
    other = list(d.rules["procedure_codes"])
    members: dict[str, dict[str, Any]] = {}
    providers: dict[str, dict[str, Any]] = {}
    for c in d.claims:
        members.setdefault(ids.member[c["member"]["member_id"]], c["member"])
        providers.setdefault(ids.provider[c["provider"]["provider_id"]], c["provider"])
    con = sqlite3.connect(payer)
    con.executescript(PAYER_SCHEMA)
    with con:
        con.execute("INSERT INTO meta VALUES ('payer_hash', 'independent-author-delivery')")
        con.executemany(
            "INSERT INTO member VALUES (?,?,?,?,?)",
            [(mid, *(m[k] for k in MEMBER_KEYS[1:])) for mid, m in members.items()],
        )
        con.executemany(
            "INSERT INTO provider VALUES (?,?,?,?)",
            [(pid, *(x[k] for k in PROVIDER_KEYS[1:])) for pid, x in providers.items()],
        )
        proc = [(c, "independent", "AUTHOR", "VISIT", i + 1, "0.00") for i, c in enumerate(visit)]
        proc += [(c, "independent", "AUTHOR", "PROC", 1, "0.00") for c in other]
        con.executemany("INSERT INTO procedure_code VALUES (?,?,?,?,?,?)", proc)
        dx_codes = sorted({code for c in d.claims for code in c["diagnoses"]})
        con.executemany(
            "INSERT INTO diagnosis_code VALUES (?,?)", [(x, "ICD-10-CM") for x in dx_codes]
        )
        con.executemany(
            "INSERT INTO bundle_pair VALUES (?,?,?)",
            [
                (b["comprehensive_code"], b["component_code"], b["exception_modifier"])
                for b in d.rules["bundle_pairs"]
            ],
        )
        con.executemany(
            "INSERT INTO unit_limit VALUES (?,?)",
            [(u["code"], u["max_units"]) for u in d.rules["unit_limits"]],
        )
        for c in d.claims:
            cid = ids.claim[c["claim_id"]]
            con.execute(
                "INSERT INTO claim VALUES (?,?,?,?,?,?,?)",
                (
                    cid,
                    ids.member[c["member"]["member_id"]],
                    ids.provider[c["provider"]["provider_id"]],
                    c["service_from"],
                    c["service_to"],
                    c["place_of_service"],
                    c["total_billed"],
                ),
            )
            con.executemany(
                "INSERT INTO claim_diagnosis VALUES (?,?,?)",
                [(cid, i, x) for i, x in enumerate(c["diagnoses"], start=1)],
            )
            for ln in c["lines"]:
                lid = f"{cid}-L{ln['line_no']}"
                con.execute(
                    "INSERT INTO claim_line VALUES (?,?,?,?,?,?,?,?)",
                    (
                        lid,
                        cid,
                        ln["line_no"],
                        ln["code"],
                        ln["units"],
                        ln["billed_amount"],
                        ln["service_date"],
                        ln["dx_pointer"],
                    ),
                )
                con.executemany(
                    "INSERT INTO line_modifier VALUES (?,?,?)",
                    [(lid, i, m) for i, m in enumerate(ln["modifiers"], start=1)],
                )
    con.close()

    lab = sqlite3.connect(labels_db)
    lab.executescript(TRUTH_SCHEMA)
    with lab:
        lab.execute("INSERT INTO meta VALUES ('truth_hash', 'independent-author-labels')")
        for row in d.labels:
            if row["label"] == "CLEAN":
                continue  # a claim with no case is clean by definition in the scorer
            aid = row["case_id"]
            lab.execute(
                "INSERT INTO anomaly_truth VALUES (?,?,?,?,?,?)",
                (
                    aid,
                    row["type"],
                    int(row["label"] == "DECOY"),
                    "author",
                    ids.provider[row["provider_id"]] if row["provider_id"] else "",
                    row["reason"],
                ),
            )
            lab.executemany(
                "INSERT INTO truth_claim VALUES (?,?,?)",
                [(aid, i, ids.claim[cid]) for i, cid in enumerate(row["claim_ids"], start=1)],
            )
    lab.close()


def interval_rows(card: Scorecard, ids: IdMap) -> list[dict[str, object]]:
    back = ids.reverse()
    rows: list[dict[str, object]] = []
    for name, t in card.types.items():
        w95 = wilson_interval(t.true_positives, t.positives) if t.positives else None
        w80 = wilson_interval(t.true_positives, t.positives, z=1.2816) if t.positives else None
        rows.append(
            {
                "type": name,
                "level": t.level,
                "positives": t.positives,
                "found": t.true_positives,
                "recall": t.recall,
                "wilson95": [w95.low, w95.high] if w95 else None,
                "wilson80": [w80.low, w80.high] if w80 else None,
                "decoys": t.decoys,
                "decoys_raised": t.decoys_raised,
                "clean": t.clean,
                "clean_raised": t.clean_raised,
                "missed": [_orig(m, back) for m in t.missed],
                "decoys_raised_ids": [back[i] for i in t.decoys_raised_ids],
                "clean_raised_ids": [back[i] for i in t.clean_raised_ids],
            }
        )
    return rows


def _orig(text: str, back: dict[str, str]) -> str:
    """Translate a repository id (possibly followed by a note) back to the author's id."""
    head, _, rest = text.partition(" ")
    return back.get(head, head) + (" " + rest if rest else "")


def case_rows(card: Scorecard, labels: list[dict[str, Any]], ids: IdMap) -> list[dict[str, object]]:
    """Per-case view of the claim-level scorecard (the scorecard counts claims; this counts cases).

    A TRUE case is found when any of its claims was raised by the matching check (the registered
    rule); `all_claims_found` is the stricter reading. A DECOY case is raised when any of its
    claims was. Provider-level cases are the provider, as in the scorecard.
    """
    out: list[dict[str, object]] = []
    back = ids.reverse()
    for typ in TYPES:
        sc = card.types[typ]
        missed_orig = [_orig(m, back) for m in sc.missed]
        decoys_orig = [back[i] for i in sc.decoys_raised_ids]
        clean_orig = [back[i] for i in sc.clean_raised_ids]
        true_cases = [r for r in labels if r["type"] == typ and r["label"] == "TRUE"]
        decoy_cases = [r for r in labels if r["type"] == typ and r["label"] == "DECOY"]
        if typ == "intensity_outlier":
            missed = {m.split(" ")[0] for m in missed_orig}
            found = [r for r in true_cases if r["provider_id"] not in missed]
            raised = [r for r in decoy_cases if r["provider_id"] in set(decoys_orig)]
            strict = len(found)
        else:
            missed_claims = set(missed_orig)
            found = [r for r in true_cases if any(c not in missed_claims for c in r["claim_ids"])]
            strict = sum(
                1 for r in true_cases if all(c not in missed_claims for c in r["claim_ids"])
            )
            raised = [r for r in decoy_cases if any(c in set(decoys_orig) for c in r["claim_ids"])]
        missed_ids = sorted(str(r["case_id"]) for r in true_cases if r not in found)
        w95 = wilson_interval(len(found), len(true_cases))
        w80 = wilson_interval(len(found), len(true_cases), z=1.2816)
        out.append(
            {
                "type": typ,
                "true_cases": len(true_cases),
                "true_cases_found": len(found),
                "all_claims_found": strict,
                "wilson95": [round(w95.low, 3), round(w95.high, 3)],
                "wilson80": [round(w80.low, 3), round(w80.high, 3)],
                "decoy_cases": len(decoy_cases),
                "decoy_cases_raised": len(raised),
                "decoy_case_ids_raised": sorted(str(r["case_id"]) for r in raised),
                "clean_claims_raised": sc.clean_raised,
                "clean_raised_ids": clean_orig,
                "missed_case_ids": missed_ids,
            }
        )
    return out


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and score an independent delivery.")
    parser.add_argument("--delivery", type=Path, default=REPO_ROOT / "eval" / "independent")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "independent")
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    delivery = load_delivery(args.delivery)
    problems = validate(delivery)
    if problems:
        print(f"INVALID: {len(problems)} problem(s); nothing was loaded or repaired.")
        for line in problems[:60]:
            print(f"- {line}")
        return 2
    print(
        f"valid: {len(delivery.claims)} claims, {len(delivery.labels)} cases "
        f"{dict(Counter((r['type'], r['label']) for r in delivery.labels))}"
    )
    if args.validate_only:
        return 0
    ids = make_id_map(delivery)
    build_stores(delivery, args.out, ids)
    (args.out / "id_map.json").write_text(
        json.dumps({"claim": ids.claim, "member": ids.member, "provider": ids.provider}) + "\n"
    )
    card = score_dataset(args.out, "independent-author delivery")
    print(render(card))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "claims_scored": card.claims_scored,
            "params": card.params,
            "params_hash": card.params_hash,
            "providers_not_scored": card.providers_not_scored,
            "other_findings": card.other_findings,
            "per_type_claims": interval_rows(card, ids),
            "per_case": case_rows(card, delivery.labels, ids),
        }
        args.json.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
