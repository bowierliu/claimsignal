"""Blind independent MODEL re-review of the KF-041 calibration prompts (2026-11-07).

    uv run python -m claims_copilot.evals.model_review prepare
    uv run python -m claims_copilot.evals.model_review ingest --response FILE --run-id ID \
        --reviewer-model M --review-method TEXT --effort TEXT --reviewed-on DATE
    uv run python -m claims_copilot.evals.model_review views

This replaces the owner's re-review (nobody has labelled the owner sheet). It is a MODEL review and
is never described as human or owner review:

* `prepare` writes a sanitized package (rubrics, the review items, the unanswered prompts, a
  response schema) for a fresh isolated reviewer. The package has no draft labels, no judge output,
  no model names, no calibration results, and no reason the items were chosen; item ids are renamed
  so the sample's gaps do not show. The id map stays outside the package.
* `ingest` validates the reviewer's structured answer deterministically (exactly one valid answer
  per prompt, nothing extra) and writes a separate derived label file stamped
  `claude-sonnet-5-5-independent-review`, plus the mixed-model reference. The original GPT Sol file
  is never opened for writing.
* `views` runs the pre-registered calibration on the original labels, the mixed-model reference,
  and a consensus-only sensitivity view, and reports every difference.

No provider call is made here; the reviewer run happens outside this module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from claims_copilot.evals.calibrate import calibrate, provenance
from claims_copilot.evals.judge import read_judgments
from claims_copilot.evals.labels import (
    DEV_RUN,
    HUMAN_CLAIMS,
    LABEL_DIR,
    LABELS_PATH,
    MODEL_REVIEW_SOURCE,
    LabelSourceError,
    validate_model_rows,
)
from claims_copilot.evals.prereg import load_preregistration
from claims_copilot.project import REPO_ROOT, RUNS_DIR

__all__ = ["LabelSourceError", "validate_model_rows"]

PACKAGE_DIR = LABEL_DIR / "blind_review_package"
ID_MAP_PATH = LABEL_DIR / "blind_review_id_map.json"
PROVENANCE_PATH = LABEL_DIR / "claude_review_provenance.json"
REVIEW_LABELS_PATH = REPO_ROOT / "eval" / "phase7_claude_review_labels.jsonl"
MIXED_LABELS_PATH = REPO_ROOT / "eval" / "phase7_mixed_model_reference_labels.jsonl"
VIEWS_PATH = REPO_ROOT / "eval" / "scorecards" / "phase7_judge_calibration_views.json"

STATEMENT_LETTERS = {"S": "SUPPORTED", "P": "PARTLY", "N": "NOT_SUPPORTED", "C": "CANNOT_TELL"}
CONFLICT_LETTERS = {"W": "WARRANTED", "N": "NOT_WARRANTED"}
PATTERN_LETTERS = {"F": "FLAG_VS_CHECK", "O": "OTHER"}
SECTIONS = {
    "statement_labels": STATEMENT_LETTERS,
    "conflict_labels": CONFLICT_LETTERS,
    "conflict_patterns": PATTERN_LETTERS,
}
SAME_FAMILY_NOTE = (
    "The reviewer (Claude Sonnet 5.5) shares a model family with the existing Claude judge "
    "(Anthropic); this review is not independent of that family."
)


class ReviewResponseError(ValueError):
    """The reviewer's answer is not exactly one valid answer per prompt."""


# ------------------------------------------------------------------------------ the package


@dataclass(frozen=True)
class Prompts:
    statements: tuple[str, ...]
    conflicts: tuple[str, ...]
    patterns: tuple[str, ...]

    @property
    def total(self) -> int:
        return len(self.statements) + len(self.conflicts) + len(self.patterns)


@dataclass(frozen=True)
class Package:
    files: dict[str, str]
    prompts: Prompts
    id_map: dict[str, str]  # package id (R01) -> sheet id (L01); never placed in the package
    sha256: str


INSTRUCTIONS = """# Independent review: instructions

You are an independent reviewer. Work only from the files in this folder:

- `review_items.md` has the items to review. Each item has a question, an answer, and the exact
  text of every source the answer cites.
- `rubrics/faithfulness.md` and `rubrics/conflict.md` define the labels.
- `response_schema.json` describes the answer format.

Do not read any other file, search for other material, or use any tool other than reading these
files. Do not use outside knowledge: judge each statement only against the source text shown
under it.

## What to answer

Every line in `review_items.md` that starts with `LABEL`, `CONFLICT` or `PATTERN` is a prompt.
Give exactly one answer for every prompt, and no answer for anything else.

- `LABEL Rnn.k` (statement): one of `S` (SUPPORTED), `P` (PARTLY), `N` (NOT_SUPPORTED),
  `C` (CANNOT_TELL). Sources are shown in full, so use `C` only when a source is missing or
  garbled; spacing quirks are not a reason.
- `CONFLICT Rnn`: `W` (the conflict status is warranted) or `N` (not warranted), by
  `rubrics/conflict.md`.
- `PATTERN Rnn`: `F` if the only disagreement the answer reports is "a screen flag says X but the
  checks found nothing to support it"; `O` for anything else.

For a conflict item, the other statements shown are context for the CONFLICT and PATTERN prompts;
they have no LABEL prompt.

Sources named like `E1.f2` are results of deterministic checks over synthetic data, shown as JSON.
Sources named like `cms-...:12-13:ab12` are passages of public documents.

## Output

Reply with ONE JSON object and nothing else (no prose before or after). Keys are prompt ids as
written in the file, for example `"R03.2"` for `LABEL R03.2` and `"R07"` for `CONFLICT R07`:

```json
{
  "statement_labels": {"R03.2": "S"},
  "conflict_labels": {"R07": "W"},
  "conflict_patterns": {"R07": "F"}
}
```

Include every prompt in `review_items.md` under the matching key.
"""


def _drop_section(text: str, heading: str) -> str:
    pattern = re.compile(rf"^## {re.escape(heading)}\n.*?(?=^## |\Z)", re.M | re.S)
    if not pattern.search(text):
        raise ValueError(f"rubric has no section {heading!r}")
    return pattern.sub("", text)


def _replace(text: str, old: str, new: str) -> str:
    """Replace `old`, matching it with any run of whitespace (the rubrics are hard-wrapped)."""
    pattern = re.compile(r"\s+".join(re.escape(w) for w in old.split()))
    if not pattern.search(text):
        raise ValueError(f"rubric no longer contains the expected text {old[:40]!r}")
    return pattern.sub(lambda _: new, text, count=1)


def _without_intro(text: str) -> str:
    """Keep the title line, drop the paragraph between the title and the first `##` heading."""
    title, _, rest = text.partition("\n")
    first = rest.find("\n## ")
    if first < 0:
        raise ValueError("rubric has no sections")
    return title + "\n" + rest[first:]


def sanitize_faithfulness(text: str) -> str:
    return _without_intro(text)


def sanitize_conflict(text: str) -> str:
    text = _without_intro(text)
    text = _drop_section(text, "Why the owner decides, not the rubric")
    text = _replace(
        text,
        "When unsure, pick the closer label and write a one-line note. Notes are for improving "
        "the definition later; they do not change the label.",
        "When unsure, pick the closer label.",
    )
    text = _replace(
        text,
        "`label`, `pattern`, and an optional one-line `note`.",
        "`label` (W or N) and `pattern` (F or O), as set out in `INSTRUCTIONS.md`. Use your own "
        "judgement for the label, and always give the pattern.",
    )
    return text


def package_hash(files: dict[str, str]) -> str:
    """sha256 over the sorted (name, sha256(content)) pairs of every file except the manifest."""
    entries = {
        name: hashlib.sha256(text.encode("utf-8")).hexdigest()
        for name, text in sorted(files.items())
        if name != "MANIFEST.json"
    }
    return hashlib.sha256(json.dumps(entries, sort_keys=True).encode("utf-8")).hexdigest()


_ITEM = re.compile(r"^ITEM (L\d\d)(\s+\(\d+ of \d+\))$")
_STATEMENT = re.compile(r"^Statement (L\d\d)\.(\d+):")
_PROMPT = re.compile(r"^(LABEL|CONFLICT|PATTERN) (L\d\d)((?:\.\d+)?) (\([A-Z/]+\)):")


def build_package(sheet_text: str, key: dict[str, Any], rubric_texts: dict[str, str]) -> Package:
    """The sanitized package. Uses only the sheet body (questions, answers, sources, prompts), the
    prompt layout from the key (never its draft or judge labels), and the two rubrics."""
    marker = "=" * 78
    start = sheet_text.find(marker)
    if start < 0:
        raise ValueError("sheet has no items")
    item_ids = sorted(key["items"], key=lambda s: int(s[1:]))
    to_package = {sheet_id: f"R{i:02d}" for i, sheet_id in enumerate(item_ids, start=1)}
    id_map = {r: sheet_id for sheet_id, r in to_package.items()}

    lines: list[str] = []
    for line in sheet_text[start:].splitlines():
        if line.startswith("NOTE "):
            continue  # an optional free-text line that could never change a label
        if m := _ITEM.match(line):
            line = f"ITEM {to_package[m.group(1)]}{m.group(2)}"
        elif m := _STATEMENT.match(line):
            line = _STATEMENT.sub(f"Statement {to_package[m.group(1)]}.{m.group(2)}:", line, 1)
        elif m := _PROMPT.match(line):
            line = f"{m.group(1)} {to_package[m.group(2)]}{m.group(3)} {m.group(4)}:"
        lines.append(line)
    items_text = "# Review items\n\n" + "\n".join(lines).rstrip("\n") + "\n"

    statements: list[str] = []
    conflicts: list[str] = []
    for sheet_id in item_ids:
        meta = key["items"][sheet_id]
        statements += [f"{to_package[sheet_id]}.{n}" for n in sorted(meta["statements"])]
        if meta.get("conflict"):
            conflicts.append(to_package[sheet_id])
    prompts = Prompts(tuple(statements), tuple(conflicts), tuple(conflicts))
    for p in statements:
        if f"LABEL {p} (" not in items_text:
            raise ValueError(f"prompt LABEL {p} is not in the sheet")
    for c in conflicts:
        for kind in ("CONFLICT", "PATTERN"):
            if f"{kind} {c} (" not in items_text:
                raise ValueError(f"prompt {kind} {c} is not in the sheet")

    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": list(SECTIONS),
        "properties": {
            "statement_labels": {
                "description": "one entry per LABEL prompt, keyed by prompt id",
                "enum_values": sorted(STATEMENT_LETTERS),
                "keys": list(prompts.statements),
            },
            "conflict_labels": {
                "description": "one entry per CONFLICT prompt, keyed by item id",
                "enum_values": sorted(CONFLICT_LETTERS),
                "keys": list(prompts.conflicts),
            },
            "conflict_patterns": {
                "description": "one entry per PATTERN prompt, keyed by item id",
                "enum_values": sorted(PATTERN_LETTERS),
                "keys": list(prompts.patterns),
            },
        },
    }
    files = {
        "INSTRUCTIONS.md": INSTRUCTIONS,
        "review_items.md": items_text,
        "rubrics/faithfulness.md": sanitize_faithfulness(rubric_texts["faithfulness"]),
        "rubrics/conflict.md": sanitize_conflict(rubric_texts["conflict"]),
        "response_schema.json": json.dumps(schema, indent=1) + "\n",
    }
    digest = package_hash(files)
    manifest = {
        "package_sha256": digest,
        "files": {
            n: hashlib.sha256(t.encode("utf-8")).hexdigest() for n, t in sorted(files.items())
        },
        "prompts": {
            "statements": list(prompts.statements),
            "conflicts": list(prompts.conflicts),
            "patterns": list(prompts.patterns),
        },
    }
    files["MANIFEST.json"] = json.dumps(manifest, indent=1) + "\n"
    return Package(files, prompts, id_map, digest)


# ------------------------------------------------------------------------------ the response


@dataclass(frozen=True)
class ParsedReview:
    statements: dict[str, str]  # "R03.2" -> SUPPORTED...
    conflicts: dict[str, str]  # "R07" -> WARRANTED / NOT_WARRANTED
    patterns: dict[str, str]  # "R07" -> FLAG_VS_CHECK / OTHER


_FENCE = re.compile(r"\A```(?:json)?[ \t]*\n(.*)\n```[ \t]*\Z", re.S)


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise ReviewResponseError(f"duplicate key {k!r}")
        out[k] = v
    return out


def validate_response(text: str, prompts: Prompts) -> ParsedReview:
    """Exactly one valid answer per prompt and nothing else. A single ```json fence around the
    object is tolerated; any other surrounding text is refused. Nothing is guessed or repaired."""
    body = text.strip()
    if m := _FENCE.match(body):
        body = m.group(1).strip()
    try:
        data = json.loads(body, object_pairs_hook=_no_duplicates)
    except ReviewResponseError:
        raise
    except json.JSONDecodeError as exc:
        raise ReviewResponseError(f"not a single JSON object: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ReviewResponseError("not a single JSON object")
    missing_sections = [s for s in SECTIONS if s not in data]
    if missing_sections:
        raise ReviewResponseError(f"missing top-level keys: {missing_sections}")
    extra_sections = sorted(set(data) - set(SECTIONS))
    if extra_sections:
        raise ReviewResponseError(f"unexpected top-level keys: {extra_sections}")
    expected = {
        "statement_labels": prompts.statements,
        "conflict_labels": prompts.conflicts,
        "conflict_patterns": prompts.patterns,
    }
    parsed: dict[str, dict[str, str]] = {}
    for section, letters in SECTIONS.items():
        block = data[section]
        if not isinstance(block, dict):
            raise ReviewResponseError(f"{section} must be an object")
        missing = [p for p in expected[section] if p not in block]
        unexpected = sorted(set(block) - set(expected[section]))
        if missing:
            raise ReviewResponseError(f"missing prompts in {section}: {missing}")
        if unexpected:
            raise ReviewResponseError(f"unexpected prompts in {section}: {unexpected}")
        parsed[section] = {}
        for prompt in expected[section]:
            value = block[prompt]
            if not isinstance(value, str) or value not in letters:
                raise ReviewResponseError(
                    f"{section} {prompt}: {value!r} is not one of {'/'.join(sorted(letters))}"
                )
            parsed[section][prompt] = letters[value]
    return ParsedReview(
        parsed["statement_labels"], parsed["conflict_labels"], parsed["conflict_patterns"]
    )


# ------------------------------------------------------------------------------ provenance, rows


@dataclass(frozen=True)
class ReviewProvenance:
    reviewer_model: str
    review_method: str
    package_sha256: str
    run_id: str
    reviewed_on: str
    effort: str
    label_source: str = MODEL_REVIEW_SOURCE

    def __post_init__(self) -> None:
        if self.label_source in HUMAN_CLAIMS or self.label_source != MODEL_REVIEW_SOURCE:
            raise ValueError(
                f"a model review cannot use the source {self.label_source!r}: it is not human"
            )
        if not re.fullmatch(r"[0-9a-f]{64}", self.package_sha256):
            raise ValueError("package_sha256 must be a sha256 hex digest")
        for name in ("reviewer_model", "review_method", "run_id", "reviewed_on", "effort"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")

    def sidecar(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "blind": True,
            "model_generated": True,
            "human_or_owner_review": False,
            "same_model_family_as_judge": True,
            "note": SAME_FAMILY_NOTE,
        }


def _row_provenance(p: ReviewProvenance) -> dict[str, Any]:
    return {
        "label_source": p.label_source,
        "owner_review": (
            "none: no owner or human review; model-generated blind independent review "
            f"({p.reviewer_model}, run {p.run_id})"
        ),
        "model_generated": True,
        "blind": True,
        "reviewer_model": p.reviewer_model,
        "review_run_id": p.run_id,
        "package_sha256": p.package_sha256,
        "review_method": p.review_method,
        "review_effort": p.effort,
        "reviewed_on": p.reviewed_on,
        "same_model_family_as_judge": True,
    }


def model_review_rows(
    parsed: ParsedReview,
    key: dict[str, Any],
    id_map: dict[str, str],
    prov: ReviewProvenance,
) -> list[dict[str, Any]]:
    """The reviewed rows only, keyed like the original label rows, stamped with the model source."""
    to_package = {sheet_id: r for r, sheet_id in id_map.items()}
    rows: list[dict[str, Any]] = []
    for sheet_id in sorted(key["items"], key=lambda s: int(s[1:])):
        meta = key["items"][sheet_id]
        r = to_package[sheet_id]
        base = {"item": sheet_id, "run_file": meta["run_file"], "stratum": meta["stratum"]}
        for n in sorted(meta["statements"]):
            rows.append(
                {
                    **base,
                    "kind": "statement",
                    "n": n,
                    "label": parsed.statements[f"{r}.{n}"],
                    **_row_provenance(prov),
                }
            )
        if meta.get("conflict"):
            rows.append(
                {
                    **base,
                    "kind": "conflict",
                    "label": parsed.conflicts[r],
                    "pattern": parsed.patterns[r],
                    **_row_provenance(prov),
                }
            )
    validate_model_rows(rows)
    return rows


# ------------------------------------------------------------------------------ merge views

RowKey = tuple[str, str, int | None]


def _key(row: dict[str, Any]) -> RowKey:
    return (row["kind"], row["run_file"], row.get("n"))


def _index(rows: list[dict[str, Any]]) -> dict[RowKey, dict[str, Any]]:
    out: dict[RowKey, dict[str, Any]] = {}
    for row in rows:
        if _key(row) in out:
            raise ValueError(f"duplicate row {_key(row)}")
        out[_key(row)] = row
    return out


def mixed_reference(
    original: list[dict[str, Any]], review_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Original rows with exactly the reviewed rows replaced by the model-review labels. Reviewed
    rows keep the original label under `original_*` for the audit trail. Inputs are not mutated."""
    validate_model_rows(review_rows)
    originals = _index(original)
    replacements = _index(review_rows)
    for k in replacements:
        if k not in originals:
            raise ValueError(f"no original row for reviewed row {k}")
    out: list[dict[str, Any]] = []
    for row in original:
        new = replacements.get(_key(row))
        if new is None:
            out.append(dict(row))
            continue
        merged = {**row, **new}
        merged["original_label"] = row["label"]
        merged["original_label_source"] = row["label_source"]
        merged["original_owner_review"] = row["owner_review"]
        if row["kind"] == "conflict":
            merged["original_pattern"] = row.get("pattern")
        out.append(merged)
    return out


def _row_disagreements(orig: dict[str, Any], new: dict[str, Any]) -> list[dict[str, str]]:
    item = orig["item"]
    if orig["kind"] == "statement":
        prompt = f"{item}.{orig['n']}"
        if orig["label"] != new["label"]:
            return [
                {
                    "prompt": prompt,
                    "kind": "statement",
                    "gpt_sol": orig["label"],
                    "claude_review": new["label"],
                }
            ]
        return []
    out = []
    if orig["label"] != new["label"]:
        out.append(
            {
                "prompt": f"{item} conflict",
                "kind": "conflict",
                "gpt_sol": orig["label"],
                "claude_review": new["label"],
            }
        )
    if orig.get("pattern") != new.get("pattern"):
        out.append(
            {
                "prompt": f"{item} pattern",
                "kind": "pattern",
                "gpt_sol": str(orig.get("pattern")),
                "claude_review": str(new.get("pattern")),
            }
        )
    return out


def disagreements(
    original: list[dict[str, Any]], review_rows: list[dict[str, Any]]
) -> list[dict[str, str]]:
    originals = _index(original)
    out: list[dict[str, str]] = []
    for new in sorted(review_rows, key=lambda r: (int(r["item"][1:]), r["kind"], r.get("n") or 0)):
        if _key(new) not in originals:
            raise ValueError(f"no original row for reviewed row {_key(new)}")
        out += _row_disagreements(originals[_key(new)], new)
    return out


def _contested(original: list[dict[str, Any]], review_rows: list[dict[str, Any]]) -> set[RowKey]:
    originals = _index(original)
    return {_key(new) for new in review_rows if _row_disagreements(originals[_key(new)], new)}


def consensus_rows(
    original: list[dict[str, Any]], review_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Strict consensus: ONLY reviewed rows where GPT Sol and the reviewer agree (a conflict row
    needs both its label and its pattern to agree). Unreviewed rows are not consensus and are
    left out; disagreements are left unresolved."""
    originals = _index(original)
    contested = _contested(original, review_rows)
    return [
        {**originals[_key(new)], "agreed_with": MODEL_REVIEW_SOURCE}
        for new in review_rows
        if _key(new) not in contested
    ]


def consensus_retained_base(
    original: list[dict[str, Any]], review_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Secondary variant: every original row except the contested reviewed rows."""
    contested = _contested(original, review_rows)
    return [dict(r) for r in original if _key(r) not in contested]


def consensus_coverage(
    original: list[dict[str, Any]], review_rows: list[dict[str, Any]]
) -> dict[str, int]:
    prompts = sum(1 if r["kind"] == "statement" else 2 for r in review_rows)
    differing = len(disagreements(original, review_rows))
    contested = _contested(original, review_rows)
    return {
        "prompts_reviewed": prompts,
        "prompts_agreed": prompts - differing,
        "prompts_disagreed": differing,
        "rows_reviewed": len(review_rows),
        "rows_in_consensus": len(review_rows) - len(contested),
        "rows_contested": len(contested),
    }


# ------------------------------------------------------------------------------ the views


def _view(rows: list[dict[str, Any]], judgments: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out = calibrate(rows, judgments)
    out["provenance"] = provenance(rows) if rows else {}
    return out


def _headline(view: dict[str, Any]) -> dict[str, Any]:
    judge = view.get("judge", {})
    conflict = view.get("conflict", {})
    return {
        "statements_labelled": view["statements_labelled"],
        "raw_agreement": view.get("raw_agreement"),
        "kappa": judge.get("kappa"),
        "false_supported": judge.get("false_supported"),
        "minority_class_statements": judge.get("minority_class_statements"),
        "accepted": judge.get("accepted"),
        "reason": judge.get("reason"),
        "conflict_labelled_answers": conflict.get("labelled_answers"),
        "conflict_judge_status": conflict.get("judge"),
    }


def calibration_views(
    original: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
    judgments: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """The original calibration, the mixed-model reference, and the consensus sensitivity views,
    side by side, with every per-prompt difference and the acceptance thresholds."""
    prereg = load_preregistration()
    mixed = mixed_reference(original, review_rows)
    consensus = consensus_rows(original, review_rows)
    retained = consensus_retained_base(original, review_rows)
    views = {
        "original_gpt_sol_draft": _view(original, judgments),
        "mixed_model_reference": _view(mixed, judgments),
        "consensus_only": _view(consensus, judgments),
        "consensus_retained_base": _view(retained, judgments),
    }
    cover = consensus_coverage(original, review_rows)
    return {
        "labels": {
            "original_gpt_sol_draft": "all 185 GPT Sol rows; the pre-existing calibration",
            "mixed_model_reference": (
                "Claude Sonnet 5.5 blind re-review replaces GPT Sol on the reviewed prompts; "
                "every other row stays GPT Sol-derived. Model labels throughout: NOT human "
                "validation and NOT a full independent relabelling."
            ),
            "consensus_only": (
                "sensitivity analysis: only reviewed rows where GPT Sol and Claude agree "
                "(conflict rows need label and pattern to agree); unreviewed rows excluded; "
                "disagreements unresolved"
            ),
            "consensus_retained_base": (
                "secondary sensitivity: the original rows minus the contested reviewed rows"
            ),
        },
        "thresholds": {
            "kappa_min": prereg.kappa_min,
            "false_supported_max": prereg.false_supported_max,
            "min_minority_class_statements": prereg.min_minority_class_statements,
            "conflict_min_labelled_answers": prereg.conflict_min_labelled_answers,
            "preregistration_sha256": prereg.sha256,
        },
        "coverage": cover,
        "consensus_coverage_of_reviewed_prompts": (
            round(cover["prompts_agreed"] / cover["prompts_reviewed"], 4)
            if cover["prompts_reviewed"]
            else None
        ),
        "disagreement_count": cover["prompts_disagreed"],
        "disagreements": disagreements(original, review_rows),
        "headline": {name: _headline(v) for name, v in views.items()},
        "views": views,
        "caveats": [
            SAME_FAMILY_NOTE,
            "Every label in every view is model-generated; none is human or owner validated.",
            "The reviewer saw full source text; the judge saw sources cut at 900 characters, so "
            "a disagreement can reflect the display cut-off rather than a judge error.",
        ],
    }


# ------------------------------------------------------------------------------ CLI


def _read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n", encoding="utf-8")


def _read_package(folder: Path) -> tuple[dict[str, str], dict[str, Any]]:
    files = {
        str(p.relative_to(folder)): p.read_text(encoding="utf-8")
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }
    manifest = json.loads(files["MANIFEST.json"])
    if package_hash(files) != manifest["package_sha256"]:
        raise ValueError("the package files do not match MANIFEST.json")
    return files, manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="claims_copilot.evals.model_review", description=__doc__)
    parser.add_argument("command", choices=("prepare", "ingest", "views"))
    parser.add_argument("--response", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--reviewer-model")
    parser.add_argument("--review-method")
    parser.add_argument("--effort")
    parser.add_argument("--reviewed-on")
    args = parser.parse_args(argv)

    if args.command == "prepare":
        if PACKAGE_DIR.exists():
            print(f"refusing: {PACKAGE_DIR.relative_to(REPO_ROOT)} already exists.")
            return 2
        sheet = (LABEL_DIR / "phase7_owner_review_sheet.md").read_text(encoding="utf-8")
        key = json.loads((LABEL_DIR / "phase7_owner_review_key.json").read_text(encoding="utf-8"))
        rubric_dir = REPO_ROOT / "eval" / "rubrics"
        pkg = build_package(
            sheet,
            key,
            {
                "faithfulness": (rubric_dir / "faithfulness_v1.md").read_text(encoding="utf-8"),
                "conflict": (rubric_dir / "conflict_v1.md").read_text(encoding="utf-8"),
            },
        )
        for name, text in pkg.files.items():
            target = PACKAGE_DIR / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        ID_MAP_PATH.write_text(json.dumps(pkg.id_map, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {PACKAGE_DIR.relative_to(REPO_ROOT)}: {pkg.prompts.total} prompts")
        print(f"package sha256 {pkg.sha256}")
        return 0

    if args.command == "ingest":
        needed = (args.response, args.run_id, args.reviewer_model, args.review_method)
        if not all(needed) or not args.effort or not args.reviewed_on:
            parser.error(
                "ingest needs --response --run-id --reviewer-model --review-method "
                "--effort --reviewed-on"
            )
        if REVIEW_LABELS_PATH.exists() or MIXED_LABELS_PATH.exists():
            print("refusing: the review labels already exist; ingest runs once per review.")
            return 2
        _, manifest = _read_package(PACKAGE_DIR)
        mp = manifest["prompts"]
        prompts = Prompts(tuple(mp["statements"]), tuple(mp["conflicts"]), tuple(mp["patterns"]))
        raw = args.response.read_text(encoding="utf-8")
        try:
            parsed = validate_response(raw, prompts)
        except ReviewResponseError as exc:
            print(f"response refused: {exc}")
            return 1
        prov = ReviewProvenance(
            reviewer_model=args.reviewer_model,
            review_method=args.review_method,
            package_sha256=manifest["package_sha256"],
            run_id=args.run_id,
            reviewed_on=args.reviewed_on,
            effort=args.effort,
        )
        key = json.loads((LABEL_DIR / "phase7_owner_review_key.json").read_text(encoding="utf-8"))
        id_map = json.loads(ID_MAP_PATH.read_text(encoding="utf-8"))
        rows = model_review_rows(parsed, key, id_map, prov)
        original = _read_rows(LABELS_PATH)
        mixed = mixed_reference(original, rows)
        _write_rows(REVIEW_LABELS_PATH, rows)
        _write_rows(MIXED_LABELS_PATH, mixed)
        sidecar = {
            **prov.sidecar(),
            "response_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "prompts": prompts.total,
            "original_labels_file_sha256": hashlib.sha256(LABELS_PATH.read_bytes()).hexdigest(),
        }
        PROVENANCE_PATH.write_text(json.dumps(sidecar, indent=1) + "\n", encoding="utf-8")
        diffs = disagreements(original, rows)
        print(
            f"{len(rows)} reviewed rows ({prompts.total} prompts); "
            f"{len(diffs)} prompts disagree with GPT Sol"
        )
        print("next: uv run python -m claims_copilot.evals.model_review views")
        return 0

    original = _read_rows(LABELS_PATH)
    if not REVIEW_LABELS_PATH.exists():
        print("no review labels yet; run ingest first.")
        return 1
    review = _read_rows(REVIEW_LABELS_PATH)
    judgments = read_judgments(RUNS_DIR / DEV_RUN / "judgments")
    result = calibration_views(original, review, judgments)
    VIEWS_PATH.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"headline": result["headline"], "coverage": result["coverage"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
