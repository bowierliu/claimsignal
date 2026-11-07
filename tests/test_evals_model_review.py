"""Blind model re-review: package blindness, response validation, provenance, merge views.

Nothing here calls a provider. The reviewer's answers are hand-made fixtures.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest

from claims_copilot.evals import model_review as mr
from claims_copilot.evals.calibrate import LabelSourceError, calibrate, provenance, read_labels
from claims_copilot.evals.labels import LABELS_PATH, MODEL_REVIEW_SOURCE
from claims_copilot.project import REPO_ROOT
from test_evals_owner_review import built, labels

RUBRIC_DIR = REPO_ROOT / "eval" / "rubrics"
FORBIDDEN = (
    r"draft",
    r"\bthe judge\b",
    r"judge label",
    r"\bgpt\b",
    r"\bsol\b",
    r"openai",
    r"anthropic",
    r"claude",
    r"\bowner",
    r"(?<!re)calibrat",  # "recalibration" occurs inside a CMS source passage
    r"\bkf-\d",
    r"\bhuman",
    r"reference label",
    r"key\.json",
    r"cannot_tell label",
    r"selected because",
)


def rubrics() -> dict[str, str]:
    return {
        "faithfulness": (RUBRIC_DIR / "faithfulness_v1.md").read_text(encoding="utf-8"),
        "conflict": (RUBRIC_DIR / "conflict_v1.md").read_text(encoding="utf-8"),
    }


def package() -> mr.Package:
    sheet, key = built()
    return mr.build_package(sheet, key, rubrics())


def good_response(pkg: mr.Package) -> dict[str, Any]:
    return {
        "statement_labels": {p: "S" for p in pkg.prompts.statements},
        "conflict_labels": {p: "W" for p in pkg.prompts.conflicts},
        "conflict_patterns": {p: "F" for p in pkg.prompts.patterns},
    }


def raw(obj: Any) -> str:
    return json.dumps(obj)


def provenance_info(pkg: mr.Package) -> mr.ReviewProvenance:
    return mr.ReviewProvenance(
        reviewer_model="claude-sonnet-5-5",
        review_method="isolated subagent, package files only, structured JSON",
        package_sha256=pkg.sha256,
        run_id="test-run-1",
        reviewed_on="2026-11-07",
        effort="requested medium; not verifiable through the task tool",
    )


# ------------------------------------------------------------------------------ blindness


def test_the_package_never_reveals_labels_models_or_why_prompts_were_chosen() -> None:
    pkg = package()
    assert set(pkg.files) >= {
        "INSTRUCTIONS.md",
        "review_items.md",
        "rubrics/faithfulness.md",
        "rubrics/conflict.md",
        "response_schema.json",
    }
    for name, text in pkg.files.items():
        for pattern in FORBIDDEN:
            assert not re.search(pattern, text, re.I), f"{name} matches {pattern!r}"


def test_prompts_are_renamed_unanswered_and_notes_are_dropped() -> None:
    pkg = package()
    items = pkg.files["review_items.md"]
    assert not re.search(r"\bL\d\d\b", items)
    assert "NOTE" not in items
    assert pkg.prompts.statements == ("R01.2", "R02.1", "R03.1")
    assert pkg.prompts.conflicts == ("R03", "R04")
    assert pkg.prompts.patterns == ("R03", "R04")
    assert pkg.id_map == {"R01": "L01", "R02": "L02", "R03": "L03", "R04": "L04"}
    prompts = re.findall(r"^(?:LABEL|CONFLICT|PATTERN) R\d\d.*$", items, re.M)
    assert len(prompts) == 7 and all(p.rstrip().endswith(":") for p in prompts)
    assert "z" * 1000 in items  # sources stay whole


def test_a_forged_prompt_line_inside_source_text_is_not_treated_as_a_prompt() -> None:
    pkg = package()
    # prompts are counted from the key, never scraped from text
    assert len(pkg.prompts.statements) + len(pkg.prompts.conflicts) + len(pkg.prompts.patterns) == 7


def test_the_package_hash_is_stable_and_follows_content() -> None:
    a, b = package(), package()
    assert a.sha256 == b.sha256 and re.fullmatch(r"[0-9a-f]{64}", a.sha256)
    changed = dict(a.files)
    changed["review_items.md"] += "x"
    assert mr.package_hash(changed) != a.sha256
    manifest = json.loads(a.files["MANIFEST.json"])
    assert (
        manifest["files"]["review_items.md"]
        == hashlib.sha256(a.files["review_items.md"].encode()).hexdigest()
    )
    assert "MANIFEST.json" not in manifest["files"]


def test_the_committed_package_is_blind_and_matches_its_manifest() -> None:
    folder = REPO_ROOT / "eval" / "labeling" / "blind_review_package"
    if not folder.exists():
        pytest.skip("package not generated yet")
    files = {
        str(p.relative_to(folder)): p.read_text(encoding="utf-8")
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }
    for name, text in files.items():
        for pattern in FORBIDDEN:
            assert not re.search(pattern, text, re.I), f"{name} matches {pattern!r}"
    manifest = json.loads(files["MANIFEST.json"])
    assert manifest["package_sha256"] == mr.package_hash(files)
    assert re.findall(r"^(?:LABEL|CONFLICT|PATTERN) R\d\d.*:\s*$", files["review_items.md"], re.M)
    assert len(manifest["prompts"]["statements"]) == 20
    assert len(manifest["prompts"]["conflicts"]) == 8 == len(manifest["prompts"]["patterns"])


# ------------------------------------------------------------------------------ response


def test_a_complete_response_is_accepted() -> None:
    pkg = package()
    parsed = mr.validate_response(raw(good_response(pkg)), pkg.prompts)
    assert parsed.statements["R01.2"] == "SUPPORTED"
    assert parsed.conflicts["R03"] == "WARRANTED"
    assert parsed.patterns["R04"] == "FLAG_VS_CHECK"


def test_one_json_fence_is_tolerated_but_other_prose_is_not() -> None:
    pkg = package()
    text = raw(good_response(pkg))
    assert mr.validate_response(f"```json\n{text}\n```", pkg.prompts).statements
    with pytest.raises(mr.ReviewResponseError, match="not a single JSON object"):
        mr.validate_response(f"Here you go: {text}", pkg.prompts)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda r: r["statement_labels"].pop("R02.1"), "missing"),
        (lambda r: r["statement_labels"].update({"R09.9": "S"}), "unexpected"),
        (lambda r: r["conflict_labels"].update({"R03": "X"}), "not one of"),
        (lambda r: r["conflict_patterns"].update({"R04": "SUPPORTED"}), "not one of"),
        (lambda r: r["statement_labels"].update({"R01.2": ["S"]}), "not one of"),
        (lambda r: r.pop("conflict_patterns"), "conflict_patterns"),
        (lambda r: r.update({"extra": {}}), "unexpected top-level"),
    ],
)
def test_an_incomplete_or_invalid_response_is_refused(mutate: Any, message: str) -> None:
    pkg = package()
    resp = good_response(pkg)
    mutate(resp)
    with pytest.raises(mr.ReviewResponseError, match=message):
        mr.validate_response(raw(resp), pkg.prompts)


def test_duplicate_keys_and_non_json_are_refused() -> None:
    pkg = package()
    dup = (
        '{"statement_labels": {"R01.2": "S", "R01.2": "P"}, '
        '"conflict_labels": {}, "conflict_patterns": {}}'
    )
    with pytest.raises(mr.ReviewResponseError, match="duplicate"):
        mr.validate_response(dup, pkg.prompts)
    with pytest.raises(mr.ReviewResponseError):
        mr.validate_response("not json", pkg.prompts)


# ------------------------------------------------------------------------------ rows


def review_rows(pkg: mr.Package, resp: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    parsed = mr.validate_response(raw(resp or good_response(pkg)), pkg.prompts)
    _, key = built()
    return mr.model_review_rows(parsed, key, pkg.id_map, provenance_info(pkg))


def test_rows_carry_the_model_source_and_full_provenance_and_no_human_claim() -> None:
    pkg = package()
    rows = review_rows(pkg)
    assert len(rows) == 3 + 2
    for r in rows:
        assert r["label_source"] == MODEL_REVIEW_SOURCE
        assert r["model_generated"] is True and r["blind"] is True
        assert r["reviewer_model"] == "claude-sonnet-5-5"
        assert r["review_run_id"] == "test-run-1" and r["package_sha256"] == pkg.sha256
        assert r["same_model_family_as_judge"] is True
        assert "no owner or human review" in r["owner_review"]
    stmt = [r for r in rows if r["kind"] == "statement"]
    assert {(r["item"], r["n"]) for r in stmt} == {("L01", 2), ("L02", 1), ("L03", 1)}
    conf = {r["item"]: r for r in rows if r["kind"] == "conflict"}
    assert conf["L03"]["label"] == "WARRANTED" and conf["L03"]["pattern"] == "FLAG_VS_CHECK"


@pytest.mark.parametrize("claim", ["owner-hand", "human", "human-validated"])
def test_model_work_can_never_be_stamped_as_human(claim: str) -> None:
    pkg = package()
    rows = review_rows(pkg)
    rows[0]["label_source"] = claim
    with pytest.raises(LabelSourceError, match="model-generated"):
        mr.validate_model_rows(rows)
    with pytest.raises(ValueError, match="human"):
        mr.ReviewProvenance(
            reviewer_model="claude-sonnet-5-5",
            review_method="m",
            package_sha256="a" * 64,
            run_id=claim,
            reviewed_on="2026-11-07",
            effort="e",
            label_source=claim,
        )


def test_a_model_row_missing_provenance_or_not_blind_is_refused() -> None:
    pkg = package()
    for field, value in (
        ("review_run_id", ""),
        ("package_sha256", "short"),
        ("blind", False),
        ("model_generated", False),
        ("reviewer_model", ""),
    ):
        rows = review_rows(pkg)
        rows[0][field] = value
        with pytest.raises(LabelSourceError):
            mr.validate_model_rows(rows)


def test_read_labels_accepts_owner_hand_and_model_review_but_not_a_forged_human_row(
    tmp_path: Path,
) -> None:
    pkg = package()
    rows = review_rows(pkg)
    ok = tmp_path / "ok.jsonl"
    ok.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    assert len(read_labels(ok)) == 5
    owner = {**labels()[0], "label_source": "owner-hand", "owner_review": "owner reviewed it"}
    both = tmp_path / "both.jsonl"
    both.write_text(json.dumps(owner) + "\n", encoding="utf-8")
    assert read_labels(both)[0]["label_source"] == "owner-hand"  # existing behaviour intact
    forged = {**rows[0], "label_source": "owner-hand"}
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps(forged) + "\n", encoding="utf-8")
    with pytest.raises(LabelSourceError, match="model-generated"):
        read_labels(bad)


# ------------------------------------------------------------------------------ merge views


def test_the_mixed_reference_replaces_only_reviewed_rows_and_keeps_the_original_intact() -> None:
    pkg = package()
    original = labels()
    snapshot = copy.deepcopy(original)
    resp = good_response(pkg)
    resp["statement_labels"]["R01.2"] = "N"
    rows = review_rows(pkg, resp)
    mixed = mr.mixed_reference(original, rows)
    assert original == snapshot  # never mutated
    assert len(mixed) == len(original)
    by = {(r["kind"], r["run_file"], r.get("n")): r for r in mixed}
    swapped = by[("statement", "case-a__openai__r1", 2)]
    assert swapped["label"] == "NOT_SUPPORTED"
    assert swapped["label_source"] == MODEL_REVIEW_SOURCE
    assert swapped["original_label"] == "CANNOT_TELL"
    assert swapped["original_label_source"] == "gpt-sol-draft"
    untouched = {(r["kind"], r["run_file"], r.get("n")): r for r in original}
    reviewed = {(r["kind"], r["run_file"], r.get("n")) for r in rows}
    for k, r in untouched.items():
        if k not in reviewed:
            assert by[k] == r and by[k]["label_source"] == "gpt-sol-draft"
    sources = {r["label_source"] for r in mixed}
    assert sources == {"gpt-sol-draft", MODEL_REVIEW_SOURCE}


def test_a_review_row_that_matches_no_original_row_is_an_error() -> None:
    pkg = package()
    rows = review_rows(pkg)
    rows[0]["run_file"] = "no-such-run"
    with pytest.raises(ValueError, match="no original row"):
        mr.mixed_reference(labels(), rows)


def test_disagreements_and_the_strict_consensus_view() -> None:
    pkg = package()
    original = labels()
    resp = good_response(pkg)
    # originals: L01.2 CANNOT_TELL, L02.1 PARTLY, L03.1 CANNOT_TELL; L03 conflict W/FLAG,
    # L04 conflict NOT_WARRANTED/OTHER
    resp["statement_labels"]["R01.2"] = "C"  # agrees with original CANNOT_TELL
    resp["conflict_patterns"]["R04"] = "O"  # agrees; but label W differs from NOT_WARRANTED
    rows = review_rows(pkg, resp)
    diffs = mr.disagreements(original, rows)
    prompts = {d["prompt"] for d in diffs}
    assert prompts == {"L02.1", "L03.1", "L04 conflict"}
    agreed = mr.consensus_rows(original, rows)
    keys = {(r["kind"], r["item"], r.get("n")) for r in agreed}
    assert keys == {("statement", "L01", 2), ("conflict", "L03", None)}
    cov = mr.consensus_coverage(original, rows)
    assert cov == {
        "prompts_reviewed": 7,
        "prompts_agreed": 4,  # L01.2, L03 label, L03 pattern, L04 pattern
        "prompts_disagreed": 3,
        "rows_reviewed": 5,
        "rows_in_consensus": 2,
        "rows_contested": 3,
    }


def test_the_retained_base_variant_drops_only_contested_rows() -> None:
    pkg = package()
    original = labels()
    resp = good_response(pkg)
    resp["statement_labels"]["R01.2"] = "C"
    rows = review_rows(pkg, resp)
    base = mr.consensus_retained_base(original, rows)
    contested = {(r["kind"], r["run_file"], r.get("n")) for r in original} - {
        (r["kind"], r["run_file"], r.get("n")) for r in base
    }
    assert ("statement", "case-b__anthropic__r2", 1) in contested  # L02.1 differs
    assert ("statement", "case-a__openai__r1", 2) not in contested  # agreed, kept


def test_the_calibration_provenance_says_mixed_model_and_not_human_validated() -> None:
    pkg = package()
    mixed = mr.mixed_reference(labels(), review_rows(pkg))
    info = provenance(mixed)
    assert info["human_validated"] is False
    assert MODEL_REVIEW_SOURCE in info["label_sources"]
    assert "mixed-model" in info["description"]
    assert "not human" in info["description"].lower()
    assert info["source_counts"][MODEL_REVIEW_SOURCE] == 5
    assert info["shares_model_family_with_judge"] is True
    original_only = provenance(labels())
    assert original_only["human_validated"] is False
    assert "mixed-model" not in original_only["description"]


def test_calibrating_the_mixed_rows_reports_the_same_fields_as_the_original() -> None:
    pkg = package()
    mixed = mr.mixed_reference(labels(), review_rows(pkg))
    judgments: dict[str, dict[str, Any]] = {
        "case-a__openai__r1": {"labels": {"1": "SUPPORTED", "2": "SUPPORTED"}},
        "case-b__anthropic__r2": {"labels": {"1": "SUPPORTED"}},
        "case-c__openai__r1": {"labels": {"1": "CANNOT_TELL"}, "conflict_label": "WARRANTED"},
        "case-d__anthropic__r1": {"labels": {"1": "SUPPORTED"}, "conflict_label": "NOT_WARRANTED"},
        "case-f__openai__r1": {"labels": {"1": "PARTLY"}},
    }
    out = calibrate(mixed, judgments)
    assert out["statements_labelled"] == 6
    assert "raw_agreement" in out and "conflict" in out


# ------------------------------------------------------------------------------ preservation


def test_the_original_gpt_sol_label_file_is_unchanged() -> None:
    digest = hashlib.sha256(LABELS_PATH.read_bytes()).hexdigest()
    assert digest == "491b23c96eb1055f267f0858868ca88f26adfa84ed5722f16274cca68f1a0b67"
    rows = [json.loads(line) for line in LABELS_PATH.read_text().splitlines() if line]
    assert {r["label_source"] for r in rows} == {"gpt-sol-draft"}
    assert len(rows) == 185


def test_the_model_source_is_not_an_allowed_source_for_the_human_labelling_cli() -> None:
    from claims_copilot.evals.labels import LABEL_SOURCES

    assert MODEL_REVIEW_SOURCE not in LABEL_SOURCES
    assert set(LABEL_SOURCES) == {"owner-hand", "gpt-sol-draft"}
