"""Owner re-review of the calibration rows that decide KF-041 (the human-label check).

    uv run python -m claims_copilot.evals.owner_review prepare   # writes the review sheet and key
    uv run python -m claims_copilot.evals.owner_review check [--sheet FILE]
    uv run python -m claims_copilot.evals.owner_review ingest --owner-review TEXT [--sheet FILE]

What is reviewed is deterministic, selected from the committed labels and the recorded judgments:
every statement the draft labelled CANNOT_TELL (19, mostly display cut-off artefacts), every
statement the judge called SUPPORTED against a non-SUPPORTED draft label (2; one of them is also a
CANNOT_TELL), and every conflict answer (8, the whole conflict reference set). The sheet is blind:
no provider, no draft label, no judge label. Sources are shown IN FULL, not cut at 900 characters,
so a "cannot tell" caused by the display cut-off becomes a real judgement; the judge still saw the
cut text, and that difference is disclosed in the calibration report.

`ingest` merges the owner's letters into `eval/phase7_model_drafted_labels.jsonl`: only the
reviewed rows change, stamped label_source="owner-hand" with the owner_review text; every other
row is left untouched. It refuses an incomplete sheet, a blank owner_review, and a second run over
rows that are already owner-hand. Nothing here writes a label by itself; only the owner's typed
letters are read. No provider call is ever made.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claims_copilot.evals.judge import answer_items, read_judgments
from claims_copilot.evals.labels import (  # same package: the sheet format and parser are shared
    _LABEL,
    DEV_RUN,
    LABEL_DIR,
    LABELS_PATH,
    MISSING,
    Parsed,
    _indent,
    _one_line,
    parse_sheet,
    stem_of,
)
from claims_copilot.evals.runner import read_run
from claims_copilot.project import REPO_ROOT, RUNS_DIR

OWNER_HAND = "owner-hand"
SUPPORTED = "SUPPORTED"
REVIEW_SHEET_PATH = LABEL_DIR / "phase7_owner_review_sheet.md"
REVIEW_KEY_PATH = LABEL_DIR / "phase7_owner_review_key.json"
REVIEWABLE_STRATA = ("ANSWERED", "CONFLICTING")


@dataclass(frozen=True)
class ReviewItem:
    """One sheet item under review: which statements (and why), and whether the conflict label."""

    item: str
    run_file: str
    stratum: str
    statements: dict[int, tuple[str, ...]]  # statement number -> selection reasons
    conflict: bool


def select_review_items(
    labels: list[dict[str, Any]], judgments: dict[str, dict[str, Any]]
) -> list[ReviewItem]:
    """The deterministic selection: CANNOT_TELL statements, false-supported statements (reference
    not SUPPORTED, judge SUPPORTED), and all conflict answers. An item can be selected for more
    than one reason. Items outside the ANSWERED/CONFLICTING strata are refused loudly: the review
    sheet has no HONEST prompt."""
    statements: dict[str, dict[int, list[str]]] = {}
    run_file_of: dict[str, str] = {}
    stratum_of: dict[str, str] = {}
    conflicts: set[str] = set()
    for row in labels:
        item = row["item"]
        run_file_of[item] = row["run_file"]
        stratum_of[item] = row["stratum"]
        if row["kind"] == "conflict":
            conflicts.add(item)
            continue
        if row["kind"] != "statement":
            continue
        reasons: list[str] = []
        if row["label"] == "CANNOT_TELL":
            reasons.append("cannot_tell")
        judge_labels = (judgments.get(row["run_file"]) or {}).get("labels") or {}
        if row["label"] != SUPPORTED and judge_labels.get(str(row["n"])) == SUPPORTED:
            reasons.append("false_supported")
        if reasons:
            statements.setdefault(item, {})[row["n"]] = reasons
    ordered = sorted(statements.keys() | conflicts, key=lambda s: int(s[1:]))
    items = [
        ReviewItem(
            item,
            run_file_of[item],
            stratum_of[item],
            {n: tuple(r) for n, r in sorted(statements.get(item, {}).items())},
            item in conflicts,
        )
        for item in ordered
    ]
    bad = [i.item for i in items if i.stratum not in REVIEWABLE_STRATA]
    if bad:
        raise ValueError(f"review items in strata outside {REVIEWABLE_STRATA}: {bad}")
    return items


# ------------------------------------------------------------------------------ the sheet

HOW_TO_REVIEW = """# Phase 7 owner re-review sheet (KF-041)

**What to do.** This sheet holds only the labels that decide whether the judge is calibrated:
every statement the draft labelled CANNOT_TELL, every statement the judge called SUPPORTED where
the draft did not, and every conflict answer. Type ONE letter after every `LABEL`, `CONFLICT` or
`PATTERN` prompt. Save the file. Then tell the assistant "review labels are done".

**Blind.** The sheet does not say who wrote an answer, what the draft label was, or what the judge
said. Do not look them up. Do not open `phase7_owner_review_key.json` until you are finished: it
records the draft and judge labels for the audit trail. Do not use outside knowledge: judge each
statement only against the source text shown under it. Rubrics are in `eval/rubrics/`
(`faithfulness_v1.md`, `conflict_v1.md`).

**Sources are shown in full.** The draft labeller and the judge saw sources cut at 900 characters,
and most CANNOT_TELL labels came from that cut-off. Here nothing is cut, so use C only when a
source is genuinely missing or garbled.

**Statement label** (`LABEL`), one letter:

| Letter | Meaning |
|---|---|
| S | SUPPORTED: a careful reader of the source alone would agree. Light rewording is fine. |
| P | PARTLY: some is in the source but part is not (extra detail, stronger claim, wrong number). |
| N | NOT_SUPPORTED: the source does not say this, differs, or the conclusion is unstated. |
| C | CANNOT_TELL: the source is missing or garbled. Use rarely; spacing quirks are not a reason. |

**Conflict items** (status CONFLICTING_EVIDENCE): `CONFLICT` W = the conflict flag is warranted,
N = not warranted. `PATTERN` F = the only disagreement reported is "a screen flag says X but the
checks found nothing to support it", O = anything else. Your own judgement decides W or N.

Conflict items also show the other labelled statements of the answer as context (no `LABEL`
prompt), so the conflict judgement sees what the draft label saw. A source already shown earlier
in the same item is not repeated ("same as above"). A `NOTE:` line is optional and never changes
a label.

Sources named like `E1.f2` are results of deterministic checks over synthetic data, shown as JSON.
Sources named like `cms-...:12-13:ab12` are passages of public policy documents.

"""


def _review_block(
    item: ReviewItem,
    position: int,
    total: int,
    record: dict[str, Any],
    shown_statements: list[int],
) -> str:
    """One item: the question, the shown statements with FULL source text (never clipped), a LABEL
    prompt only for each reviewed statement, and CONFLICT/PATTERN prompts for a conflict item."""
    answer = record["answer"]
    lines = [
        "=" * 78,
        f"ITEM {item.item}   ({position} of {total})",
        f"Question the investigator asked: {_one_line(record['question'])}",
        f"Answer status shown: {answer['status']}",
        "-" * 78,
    ]
    by_n = {it.n: it for it in answer_items(record)}
    seen: set[str] = set()
    for n in shown_statements:
        it = by_n.get(n)
        if it is None:
            raise ValueError(f"{item.run_file} has no statement {n}")
        lines.append(f"Statement {item.item}.{it.n}: {_one_line(it.text)}")
        for citation, text in it.sources:
            if citation in seen:
                lines.append(f"  Cited source {citation}: (same as above)")
                continue
            seen.add(citation)
            lines.append(f"  Cited source {citation}:")
            lines.append(_indent(text if text is not None else MISSING, "      "))
        if it.n in item.statements:
            lines.append(f"LABEL {item.item}.{it.n} (S/P/N/C): ")
            lines.append("")
    if item.conflict:
        lines.append(f"CONFLICT {item.item} (W/N): ")
        lines.append(f"PATTERN {item.item} (F/O): ")
    lines.append(f"NOTE {item.item}: ")
    lines.append("")
    return "\n".join(lines)


def build_review_sheet(
    items: list[ReviewItem],
    labels: list[dict[str, Any]],
    judgments: dict[str, dict[str, Any]],
    records: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    """The blind sheet and the audit key. The key records run file, strata, selection reasons, and
    the draft and judge labels (kept apart from the sheet, like the original label key)."""
    labeled_by_item: dict[str, list[int]] = {}
    draft_by_item: dict[str, dict[str, Any]] = {}
    for row in labels:
        if row["kind"] == "statement":
            labeled_by_item.setdefault(row["item"], []).append(row["n"])
            draft_by_item.setdefault(row["item"], {}).setdefault("statements", {})[row["n"]] = row[
                "label"
            ]
        elif row["kind"] == "conflict":
            draft_by_item.setdefault(row["item"], {})["conflict"] = row["label"]
            draft_by_item[row["item"]]["pattern"] = row["pattern"]
    blocks: list[str] = []
    key_items: dict[str, Any] = {}
    shown_total = 0
    for position, item in enumerate(items, start=1):
        record = records.get(item.run_file)
        if record is None:
            raise ValueError(f"no recorded run for {item.run_file}")
        # A statement is judged against its own cited sources, so non-conflict items show only the
        # reviewed statements; a conflict judgement covers the whole answer, so conflict items also
        # show the other labelled statements (what the draft label saw).
        shown = sorted(
            set(item.statements)
            | (set(labeled_by_item.get(item.item, [])) if item.conflict else set())
        )
        shown_total += len(shown)
        blocks.append(_review_block(item, position, len(items), record, shown))
        judge_labels = (judgments.get(item.run_file) or {}).get("labels") or {}
        key_items[item.item] = {
            "run_file": item.run_file,
            "stratum": item.stratum,
            "statements": sorted(item.statements),
            "conflict": item.conflict,
            "reasons": {str(n): list(reasons) for n, reasons in item.statements.items()},
            "shown_statements": shown,
            "draft": draft_by_item.get(item.item, {}),
            "judge": {str(n): judge_labels.get(str(n)) for n in item.statements},
        }
    n_statements = sum(len(i.statements) for i in items)
    n_conflicts = sum(1 for i in items if i.conflict)
    minutes = max(1, round((shown_total * 25 + n_conflicts * 30) / 60))
    head = HOW_TO_REVIEW + (
        f"This sheet has {len(items)} items: {n_statements} statements to label and "
        f"{n_conflicts} conflict answers (about {minutes} minutes).\n\n"
    )
    key = {
        "run": DEV_RUN,
        "purpose": (
            "KF-041 owner re-review: CANNOT_TELL and false-supported statements, conflict answers"
        ),
        "selection_counts": {
            reason: sum(1 for i in items for r in i.statements.values() if reason in r)
            for reason in ("cannot_tell", "false_supported")
        }
        | {"conflict": n_conflicts},
        "items": key_items,
    }
    return head + "\n".join(blocks), key


# ------------------------------------------------------------------------------ the merge


@dataclass(frozen=True)
class MergeReport:
    replaced: int
    changed: tuple[str, ...]  # one line per row whose label content changed


def merge_labels(
    labels: list[dict[str, Any]],
    parsed: Parsed,
    key: dict[str, Any],
    *,
    owner_review: str,
) -> tuple[list[dict[str, Any]], MergeReport]:
    """Replace only the reviewed rows, stamped owner-hand; every other row is returned unchanged.
    Refuses a blank owner_review, a target row that is already owner-hand, and a key entry that
    matches no row."""
    if not owner_review.strip():
        raise ValueError("owner_review must say what review was done")
    targets: dict[tuple[str, str, int | None], tuple[str, dict[str, Any]]] = {}
    for item_id, meta in sorted(key["items"].items()):
        for n in meta["statements"]:
            targets[("statement", meta["run_file"], n)] = (
                item_id,
                {"label": parsed.statements[f"{item_id}.{n}"]},
            )
        if meta.get("conflict"):
            targets[("conflict", meta["run_file"], None)] = (
                item_id,
                {"label": parsed.conflict[item_id], "pattern": parsed.pattern[item_id]},
            )
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int | None]] = set()
    changed: list[str] = []
    problems: list[str] = []
    for row in labels:
        target_key = (row["kind"], row["run_file"], row.get("n"))
        if target_key not in targets:
            out.append(row)
            continue
        seen.add(target_key)
        item_id, fields = targets[target_key]
        if row["label_source"] == OWNER_HAND:
            problems.append(f"{item_id} ({row['kind']}) is already {OWNER_HAND}")
            out.append(row)
            continue
        old = ", ".join(str(row[f]) for f in sorted(fields))
        new = ", ".join(str(fields[f]) for f in sorted(fields))
        if old != new:
            changed.append(f"{item_id} {row['kind']}: {old} -> {new}")
        out.append({**row, **fields, "label_source": OWNER_HAND, "owner_review": owner_review})
    problems += [f"no row matches {k}" for k in targets if k not in seen]
    if problems:
        raise ValueError("; ".join(problems))
    return out, MergeReport(len(seen), tuple(changed))


# ------------------------------------------------------------------------------ CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="claims_copilot.evals.owner_review", description=__doc__)
    parser.add_argument("command", choices=("prepare", "check", "ingest"))
    parser.add_argument("--sheet", type=Path, default=REVIEW_SHEET_PATH)
    parser.add_argument("--owner-review")
    args = parser.parse_args(argv)

    if args.command == "prepare":
        labels = [
            json.loads(line)
            for line in LABELS_PATH.read_text(encoding="utf-8").splitlines()
            if line
        ]
        judgments = read_judgments(RUNS_DIR / DEV_RUN / "judgments")
        records = {stem_of(r): r["record"] for r in read_run(RUNS_DIR / DEV_RUN)}
        items = select_review_items(labels, judgments)
        sheet, key = build_review_sheet(items, labels, judgments, records)
        LABEL_DIR.mkdir(parents=True, exist_ok=True)
        if REVIEW_SHEET_PATH.exists() and any(
            (m := _LABEL.match(line)) and m.group(3).strip()
            for line in REVIEW_SHEET_PATH.read_text(encoding="utf-8").splitlines()
        ):
            print("refusing: the sheet already has typed answers; move it first.")
            return 2
        REVIEW_SHEET_PATH.write_text(sheet, encoding="utf-8")
        REVIEW_KEY_PATH.write_text(json.dumps(key, indent=1) + "\n", encoding="utf-8")
        counts = key["selection_counts"]
        print(f"wrote {REVIEW_SHEET_PATH.relative_to(REPO_ROOT)}: {len(items)} items, {counts}")
        print("the sheet is blind and shows full source text; the key holds the audit trail.")
        return 0

    key = json.loads(REVIEW_KEY_PATH.read_text(encoding="utf-8"))
    parsed = parse_sheet(args.sheet.read_text(encoding="utf-8"), key)
    if parsed.problems:
        for p in parsed.problems[:40]:
            print(p)
        print(f"{len(parsed.problems)} problem(s); fix them in {args.sheet.name} and re-run.")
        return 1
    if args.command == "check":
        print("sheet is complete and valid")
        return 0
    if not args.owner_review or not args.owner_review.strip():
        parser.error("ingest needs --owner-review (what review was done)")
    labels = [
        json.loads(line) for line in LABELS_PATH.read_text(encoding="utf-8").splitlines() if line
    ]
    out, report = merge_labels(labels, parsed, key, owner_review=args.owner_review)
    LABELS_PATH.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in out) + "\n", encoding="utf-8"
    )
    print(f"replaced {report.replaced} reviewed rows with owner-hand labels;")
    print(f"{len(labels) - report.replaced} rows untouched.")
    if report.changed:
        print("labels that differ from the draft:")
        for line in report.changed:
            print(f"  {line}")
    else:
        print("every owner label agrees with the draft.")
    print("next: uv run python -m claims_copilot.evals.calibrate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
