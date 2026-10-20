"""The owner's calibration labels: choose the sample, write the sheet, read the labelled sheet.

    uv run python -m claims_copilot.evals.labels prepare   # writes the sheet and the key
    uv run python -m claims_copilot.evals.labels check     # tells what is still unlabelled
    uv run python -m claims_copilot.evals.labels ingest    # writes eval/phase7_hand_labels.jsonl

The sample is fixed by the pre-registration: 40 development-split answers, seed 7, mix 24
ANSWERED, 8 CONFLICTING_EVIDENCE, 8 INSUFFICIENT_EVIDENCE or other, both providers represented.
The sheet is blind: it does not say which provider or model wrote an answer, and items are shuffled
so strata are not grouped. The key (item -> run file) is kept apart. Nothing here writes a label:
`ingest` only reads what the owner typed, and refuses an unfinished sheet.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from dataclasses import dataclass
from typing import Any

from claims_copilot.evals.judge import Item, answer_items, clip
from claims_copilot.evals.prereg import load_preregistration
from claims_copilot.evals.runner import read_run
from claims_copilot.project import REPO_ROOT, RUNS_DIR

LABEL_DIR = REPO_ROOT / "eval" / "labeling"
SHEET_PATH = LABEL_DIR / "phase7_label_sheet.md"
KEY_PATH = LABEL_DIR / "phase7_label_key.json"
HAND_LABELS_PATH = REPO_ROOT / "eval" / "phase7_hand_labels.jsonl"
DEV_RUN = "p7-dev-lexical"

FAITH = {"S": "SUPPORTED", "P": "PARTLY", "N": "NOT_SUPPORTED", "C": "CANNOT_TELL"}
CONFLICT = {"W": "WARRANTED", "N": "NOT_WARRANTED"}
PATTERN = {"F": "FLAG_VS_CHECK", "O": "OTHER"}
HONEST = {"Y": "HONEST", "N": "NOT_HONEST"}
ANSWERED, CONFLICTING = "ANSWERED", "CONFLICTING_EVIDENCE"
MAX_STATEMENTS_PER_ANSWER = 6  # amendment A3: a long answer is labelled on a seeded subset of 6


def stem_of(row: dict[str, Any]) -> str:
    j = row["job"]
    return f"{j['case_id']}__{j['provider']}__r{j['repeat']}"


def stratum(row: dict[str, Any]) -> str:
    answer = row["record"]["answer"]
    status = answer["status"]
    if status == ANSWERED and answer["summary"]:
        return "ANSWERED"
    if status == CONFLICTING and answer["summary"]:
        return "CONFLICTING"
    if status == "INSUFFICIENT_EVIDENCE" or (
        status == "OUT_OF_SCOPE" and row["record"].get("limit") != "scope_gate"
    ):
        return "OTHER"
    return "NONE"  # gated refusals, invalid outputs, empty answers: nothing to label


def _take(pool: list[dict[str, Any]], n: int, rng: random.Random) -> list[dict[str, Any]]:
    """n rows from `pool`: one per case first, providers alternating, all seeded."""
    by_provider: dict[str, list[dict[str, Any]]] = {}
    for row in sorted(pool, key=stem_of):
        by_provider.setdefault(row["job"]["provider"], []).append(row)
    for rows in by_provider.values():
        rng.shuffle(rows)
    order: list[dict[str, Any]] = []
    queues = [by_provider[p] for p in sorted(by_provider)]
    while any(queues):
        for q in queues:
            if q:
                order.append(q.pop())
    chosen: list[dict[str, Any]] = []
    seen_cases: set[str] = set()
    for row in order:  # first pass: at most one run per case
        if len(chosen) < n and row["job"]["case_id"] not in seen_cases:
            chosen.append(row)
            seen_cases.add(row["job"]["case_id"])
    for row in order:  # second pass: repeats of a case, if the pool is short
        if len(chosen) < n and row not in chosen:
            chosen.append(row)
    return chosen


@dataclass(frozen=True)
class Sample:
    rows: list[dict[str, Any]]
    shortfalls: dict[str, int]  # stratum -> how many fewer than the mix asked for


def select_sample(rows: list[dict[str, Any]], mix: dict[str, int], seed: int) -> Sample:
    """The pre-registered mix. A stratum that has too few answers is topped up from ANSWERED, and
    the shortfall is reported in the sheet and key (a deterministic rule, written down here)."""
    rng = random.Random(seed)  # noqa: S311  (seeded sampling, not security)
    pools: dict[str, list[dict[str, Any]]] = {"ANSWERED": [], "CONFLICTING": [], "OTHER": []}
    for row in rows:
        s = stratum(row)
        if s in pools:
            pools[s].append(row)
    want = {
        "ANSWERED": mix["ANSWERED"],
        "CONFLICTING": mix["CONFLICTING_EVIDENCE"],
        "OTHER": mix["INSUFFICIENT_EVIDENCE_or_other"],
    }
    chosen: dict[str, list[dict[str, Any]]] = {}
    shortfalls: dict[str, int] = {}
    for name in ("CONFLICTING", "OTHER", "ANSWERED"):
        n = want[name] + sum(shortfalls.values()) * (name == "ANSWERED")
        got = _take(pools[name], n, rng)
        chosen[name] = got
        if len(got) < n and name != "ANSWERED":
            shortfalls[name] = n - len(got)
    selected = chosen["CONFLICTING"] + chosen["OTHER"] + chosen["ANSWERED"]
    rng.shuffle(selected)
    return Sample(selected, shortfalls)


def labelled_statements(row: dict[str, Any]) -> list[int]:
    """Which statement numbers of an answer go on the sheet: all of them, or a seeded sample of
    MAX_STATEMENTS_PER_ANSWER (random, so position does not bias which statements are labelled)."""
    numbers = [it.n for it in answer_items(row["record"])]
    if len(numbers) <= MAX_STATEMENTS_PER_ANSWER:
        return numbers
    rng = random.Random(f"phase7-label-statements:{stem_of(row)}")  # noqa: S311
    return sorted(rng.sample(numbers, MAX_STATEMENTS_PER_ANSWER))


# ------------------------------------------------------------------------------ the sheet

HOW_TO = """# Phase 7 hand-labelling sheet

**What to do (about an hour).** Read each item, and type ONE letter after every `LABEL`, `CONFLICT`,
`PATTERN` or `HONEST` prompt. Save the file. Then tell the assistant "labels are done".
Do not look up who wrote an answer (the sheet does not say). Do not use outside knowledge: judge
each statement only against the source text shown under it. Rubrics are in `eval/rubrics/`
(`faithfulness_v1.md`, `conflict_v1.md`).

**Statement label** (`LABEL`), one letter:

| Letter | Meaning |
|---|---|
| S | SUPPORTED: a careful reader of the source alone would agree. Light rewording is fine. |
| P | PARTLY: some is in the source but part is not (extra detail, stronger claim, wrong number). |
| N | NOT_SUPPORTED: the source does not say this, differs, or the conclusion is unstated. |
| C | CANNOT_TELL: the source is cut off or garbled. Use rarely; spacing quirks are not a reason. |

**Conflict items** (status CONFLICTING_EVIDENCE): `CONFLICT` W = the conflict flag is warranted,
N = not warranted. `PATTERN` F = the only disagreement reported is "a screen flag says X but the
checks found nothing to support it", O = anything else. Your own judgement decides W or N.

**Honest non-answer items** (status INSUFFICIENT_EVIDENCE and similar): `HONEST` Y = a reader
would correctly understand that the sources do not cover the question and nothing unrelated is
presented as support; N = it is misleading or presents unrelated text as support.

A source can be long and is cut at 900 characters ("more characters not shown"); if the part you
need is cut off, use C. A source already shown earlier in the same item is not repeated ("same as
above"). Answers with more than 6 statements show a seeded random 6 of them (the numbers skip), to
keep the sitting short. A `NOTE:` line is optional and never changes a label.

Sources named like `E1.f2` are results of deterministic checks over synthetic data, shown as JSON.
Sources named like `cms-...:12-13:ab12` are passages of public policy documents.

"""


MISSING = "(this id does not resolve to any source)"


def _one_line(text: str) -> str:
    """Data never starts a line of its own at column 0, so it cannot forge a label prompt."""
    return " ".join(text.split())


def _indent(text: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + line for line in text.splitlines()) or prefix


def _item_block(item_id: str, total: int, row: dict[str, Any], strat: str) -> str:
    record = row["record"]
    answer = record["answer"]
    lines = [
        "=" * 78,
        f"ITEM {item_id}   ({int(item_id[1:])} of {total})",
        f"Question the investigator asked: {_one_line(record['question'])}",
        f"Answer status shown: {answer['status']}",
        "-" * 78,
    ]
    shown = set(labelled_statements(row))
    items: list[Item] = [it for it in answer_items(record) if it.n in shown]
    seen: set[str] = set()
    for it in items:
        lines.append(f"Statement {item_id}.{it.n}: {_one_line(it.text)}")
        for citation, text in it.sources:
            if citation in seen:
                lines.append(f"  Cited source {citation}: (same as above)")
                continue
            seen.add(citation)
            body = clip(text) if text is not None else MISSING
            lines.append(f"  Cited source {citation}:")
            lines.append(_indent(body, "      "))
        lines.append(f"LABEL {item_id}.{it.n} (S/P/N/C): ")
        lines.append("")
    if strat == "CONFLICTING":
        lines.append(f"CONFLICT {item_id} (W/N): ")
        lines.append(f"PATTERN {item_id} (F/O): ")
    if strat == "OTHER":
        searched = "; ".join(answer.get("searched", [])[:6]) or "(nothing recorded)"
        lines.append(f"What the system searched: {searched}")
        lines.append(f"HONEST {item_id} (Y/N): ")
    lines.append(f"NOTE {item_id}: ")
    lines.append("")
    return "\n".join(lines)


def build_sheet(sample: Sample) -> tuple[str, dict[str, Any]]:
    total = len(sample.rows)
    blocks = []
    key_items: dict[str, Any] = {}
    n_statements = 0
    for i, row in enumerate(sample.rows, start=1):
        item_id = f"L{i:02d}"
        strat = stratum(row)
        numbers = labelled_statements(row)
        n_statements += len(numbers)
        key_items[item_id] = {
            "run_file": stem_of(row),
            "stratum": strat,
            "statements": numbers,
            "of": len(answer_items(row["record"])),
        }
        blocks.append(_item_block(item_id, total, row, strat))
    head = HOW_TO + (
        f"This sheet has {total} items and {n_statements} statements to label "
        f"(about {max(1, round(n_statements * 25 / 60))} minutes at 25 seconds each).\n\n"
    )
    key = {
        "run": DEV_RUN,
        "seed": load_preregistration().label_sample_seed,
        "shortfalls": sample.shortfalls,
        "items": key_items,
    }
    return head + "\n".join(blocks), key


# ------------------------------------------------------------------------------ reading it back

_LABEL = re.compile(
    r"^(LABEL|CONFLICT|PATTERN|HONEST)\s+(L\d{2}(?:\.\d+)?)\s*\([A-Z/]+\)\s*:\s*(.*)$"
)


@dataclass(frozen=True)
class Parsed:
    statements: dict[str, str]  # "L07.2" -> SUPPORTED...
    conflict: dict[str, str]
    pattern: dict[str, str]
    honest: dict[str, str]
    problems: list[str]


def parse_sheet(text: str, key: dict[str, Any]) -> Parsed:
    tables = {"LABEL": FAITH, "CONFLICT": CONFLICT, "PATTERN": PATTERN, "HONEST": HONEST}
    got: dict[str, dict[str, str]] = {k: {} for k in tables}
    problems: list[str] = []
    for line in text.splitlines():
        m = _LABEL.match(line)
        if not m:
            continue
        kind, ident, raw = m.groups()
        raw = raw.strip().upper()
        if not raw:
            continue
        if len(raw) != 1 or raw not in tables[kind]:
            problems.append(f"{kind} {ident}: {raw!r} is not one of {'/'.join(tables[kind])}")
            continue
        got[kind][ident] = tables[kind][raw]
    # What must be there, from the key.
    for item_id, meta in key["items"].items():
        for n in meta["statements"]:
            if f"{item_id}.{n}" not in got["LABEL"]:
                problems.append(f"LABEL {item_id}.{n} is empty")
        if meta["stratum"] == "CONFLICTING":
            for kind in ("CONFLICT", "PATTERN"):
                if item_id not in got[kind]:
                    problems.append(f"{kind} {item_id} is empty")
        if meta["stratum"] == "OTHER" and item_id not in got["HONEST"]:
            problems.append(f"HONEST {item_id} is empty")
    return Parsed(got["LABEL"], got["CONFLICT"], got["PATTERN"], got["HONEST"], problems)


def hand_label_rows(parsed: Parsed, key: dict[str, Any]) -> list[dict[str, Any]]:
    """Rows for `eval/phase7_hand_labels.jsonl`. Written only from an owner-filled sheet."""
    rows: list[dict[str, Any]] = []
    for item_id, meta in sorted(key["items"].items()):
        base = {"item": item_id, "run_file": meta["run_file"], "stratum": meta["stratum"]}
        for n in meta["statements"]:
            rows.append(
                {
                    **base,
                    "kind": "statement",
                    "n": n,
                    "of": meta["of"],
                    "label": parsed.statements[f"{item_id}.{n}"],
                }
            )
        if item_id in parsed.conflict:
            rows.append(
                {
                    **base,
                    "kind": "conflict",
                    "label": parsed.conflict[item_id],
                    "pattern": parsed.pattern[item_id],
                }
            )
        if item_id in parsed.honest:
            rows.append({**base, "kind": "honest", "label": parsed.honest[item_id]})
    for r in rows:
        r["labeller"] = "owner"
    return rows


# ------------------------------------------------------------------------------ CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="claims_copilot.evals.labels", description=__doc__)
    parser.add_argument("command", choices=("prepare", "check", "ingest"))
    args = parser.parse_args(argv)

    if args.command == "prepare":
        prereg = load_preregistration()
        rows = [r for r in read_run(RUNS_DIR / DEV_RUN) if r["job"]["split"] == "dev"]
        sample = select_sample(rows, prereg.label_sample_mix, prereg.label_sample_seed)
        sheet, key = build_sheet(sample)
        LABEL_DIR.mkdir(parents=True, exist_ok=True)
        if SHEET_PATH.exists() and any(
            _LABEL.match(line) and _LABEL.match(line).group(3).strip()  # type: ignore[union-attr]
            for line in SHEET_PATH.read_text(encoding="utf-8").splitlines()
        ):
            print("refusing: the sheet already has typed answers; move it first.")
            return 2
        SHEET_PATH.write_text(sheet, encoding="utf-8")
        KEY_PATH.write_text(json.dumps(key, indent=1) + "\n", encoding="utf-8")
        strata = {
            s: sum(1 for m in key["items"].values() if m["stratum"] == s)
            for s in ("ANSWERED", "CONFLICTING", "OTHER")
        }
        print(f"wrote {SHEET_PATH.relative_to(REPO_ROOT)}: {len(sample.rows)} items {strata}")
        print(f"shortfalls (topped up from ANSWERED): {sample.shortfalls or 'none'}")
        return 0

    key = json.loads(KEY_PATH.read_text(encoding="utf-8"))
    parsed = parse_sheet(SHEET_PATH.read_text(encoding="utf-8"), key)
    if parsed.problems:
        for p in parsed.problems[:40]:
            print(p)
        print(f"{len(parsed.problems)} problem(s); fix them in {SHEET_PATH.name} and re-run.")
        return 1
    if args.command == "check":
        print("sheet is complete and valid")
        return 0
    rows = hand_label_rows(parsed, key)
    HAND_LABELS_PATH.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(rows)} owner label rows to {HAND_LABELS_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
