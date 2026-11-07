from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from claims_copilot.evals import intensity_v2 as iv
from claims_copilot.project import REPO_ROOT
from claims_copilot.tools import patterns_v2 as v2

CODES = ["X0001", "X0002", "X0003", "X0004"]


def counts(total: int, high: int) -> dict[str, int]:
    rest = total - high
    a = rest // 3
    return {"X0001": a, "X0002": a, "X0003": rest - 2 * a, "X0004": high}


def write(
    directory: Path,
    providers: list[tuple[str, str, int, int, str, str | None, str | None]],
    stratum: str = "primary",
) -> Path:
    """providers: (id, specialty, lines, high, label, severity, decoy_kind)."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "rules.json").write_text(json.dumps({"visit_codes": CODES}))
    (directory / "AUTHOR_NOTE.md").write_text("note\n")
    prow, lrow = [], []
    for pid, spec, n, high, label, sev, kind in providers:
        prow.append({"provider_id": pid, "specialty": spec, "visit_counts": counts(n, high)})
        lrow.append(
            {
                "provider_id": pid,
                "specialty": spec,
                "stratum": stratum,
                "label": label,
                "severity": sev,
                "decoy_kind": kind,
                "intended_high_share": round(high / n, 3),
                "reason": "test",
            }
        )
    (directory / "providers.jsonl").write_text("\n".join(json.dumps(r) for r in prow) + "\n")
    (directory / "labels.jsonl").write_text("\n".join(json.dumps(r) for r in lrow) + "\n")
    return directory


def small_world() -> list[tuple[str, str, int, int, str, str | None, str | None]]:
    rows: list[tuple[str, str, int, int, str, str | None, str | None]] = []
    for i in range(30):  # ordinary: shares about 10% to 38% on 100 lines
        rows.append((f"O{i:02d}", "S1", 100, 10 + (i % 15) * 2, "ORDINARY", None, None))
    rows += [
        ("T1", "S1", 100, 75, "TRUE", "strong", None),
        ("T2", "S1", 100, 60, "TRUE", "mild", None),
        ("T3", "S1", 20, 18, "TRUE", "strong", None),  # below the volume floor
        ("D1", "S1", 100, 40, "DECOY", None, "hard"),
        ("D2", "S1", 100, 30, "DECOY", None, "easy"),
    ]
    return rows


def test_a_well_formed_small_fixture_has_no_schema_problems_but_reports_requirement_gaps(
    tmp_path: Path,
) -> None:
    fx = iv.load_fixture(write(tmp_path, small_world()))
    val = iv.validate(fx)
    assert val.schema_problems == []
    assert any("need at least 3 primary specialties" in g for g in val.requirement_gaps)
    assert any("no contamination stratum" in g for g in val.requirement_gaps)


def test_schema_problems_block_and_are_all_listed(tmp_path: Path) -> None:
    d = write(tmp_path, small_world())
    lines = (d / "labels.jsonl").read_text().splitlines()
    bad = json.loads(lines[0])
    bad["label"] = "MAYBE"
    lines[0] = json.dumps(bad)
    lines.append(json.dumps({**json.loads(lines[1]), "provider_id": "GHOST"}))
    (d / "labels.jsonl").write_text("\n".join(lines) + "\n")
    val = iv.validate(iv.load_fixture(d))
    joined = "\n".join(val.schema_problems)
    assert "label 'MAYBE' not allowed" in joined
    assert "label for unknown provider GHOST" in joined


def test_missing_files_are_reported(tmp_path: Path) -> None:
    fx = iv.load_fixture(tmp_path)
    assert "missing file: labels.jsonl" in fx.problems


def test_scoring_counts_flags_abstentions_and_denominators(tmp_path: Path) -> None:
    fx = iv.load_fixture(write(tmp_path / "fx", small_world()))
    ids = iv.provider_id_map(fx)
    repo = iv.build_repository(fx, tmp_path / "out", ids)
    report = iv.score_fixture(fx, repo, ids)
    rows = {r["provider_id"]: r for r in report["per_provider"]}
    assert rows["T3"]["scorable"] is False
    assert rows["T3"]["v1"]["outcome"] == "abstain"
    assert rows["T3"]["v2"] == {"outcome": "abstain", "reason": "subject_below_min_volume"}
    assert rows["T1"]["v2"]["outcome"] == "flag"
    assert rows["O00"]["v2"]["outcome"] == "no_flag"
    prim = report["primary"]["v2"]
    assert prim["recall"]["n"] == 2  # T3 is not scorable and is outside the primary denominator
    assert prim["false_positive_rate"]["n"] == 30 + 2
    allt = report["secondary"]["v2"]["recall_all_true_including_below_floor"]
    assert allt["n"] == 3
    assert allt["abstentions"] == {"subject_below_min_volume": 1}
    # the v2 result from the repository path agrees with the pure function on the same counts
    mixes = repo.visit_mix()
    subject = next(m for m in mixes if m.provider_id == ids["T1"])
    assert v2.assess(subject, mixes).decision == "flag"


def test_the_store_holds_no_labels_and_one_claim_per_visit_line(tmp_path: Path) -> None:
    fx = iv.load_fixture(write(tmp_path / "fx", small_world()))
    ids = iv.provider_id_map(fx)
    repo = iv.build_repository(fx, tmp_path / "out", ids)
    total = sum(iv.lines_of(r) for r in fx.providers)
    n = repo.visit_mix()
    assert sum(m.visit_lines for m in n) == total
    text = (tmp_path / "out" / "payer.sqlite").read_bytes()
    assert b"DECOY" not in text and b"ORDINARY" not in text


def gates_report(r1: float, r2: float, f2: float, a1: int, a2: int) -> dict[str, Any]:
    def side(recall: float, fpr: float, alarms: int) -> dict[str, Any]:
        return {
            "recall": {"rate": recall},
            "false_positive_rate": {"rate": fpr},
            "false_alarm_count": alarms,
        }

    return {"primary": {"v1": side(r1, 0.0, a1), "v2": side(r2, f2, a2)}}


def test_gates_pass_only_when_all_registered_conditions_hold() -> None:
    prereg = json.loads(iv.PREREG_PATH.read_text())
    ok = iv.evaluate_gates(gates_report(0.2, 0.8, 0.05, 3, 3), prereg)
    assert ok["all_passed"] is True
    edge = iv.evaluate_gates(gates_report(0.6, 0.8, 0.05, 3, 3), prereg)  # exactly +0.20
    assert edge["all_passed"] is True
    for bad in (
        gates_report(0.2, 0.79, 0.0, 3, 3),  # recall under 0.80
        gates_report(0.66, 0.85, 0.0, 3, 3),  # improvement under 0.20
        gates_report(0.2, 0.9, 0.0501, 3, 3),  # FP rate above 0.05
        gates_report(0.2, 0.9, 0.0, 3, 4),  # more false alarms than v1
    ):
        res = iv.evaluate_gates(bad, prereg)
        assert res["all_passed"] is False
        assert "stays experimental" in res["decision"]


# --- the pre-registration is consistent with the code and the committed documents -------------


def test_preregistered_constants_equal_the_module_constants() -> None:
    prereg = json.loads(iv.PREREG_PATH.read_text())
    c = prereg["v2"]["constants"]
    assert c == {
        "MIN_VISIT_LINES": v2.MIN_VISIT_LINES,
        "MIN_PEERS": v2.MIN_PEERS,
        "ALPHA_FAMILY": v2.ALPHA_FAMILY,
        "P0_FLOOR": v2.P0_FLOOR,
        "P0_CAP": v2.P0_CAP,
        "MIN_GAP_ABOVE_P75": v2.MIN_GAP_ABOVE_P75,
        "PEER_MEDIAN_ABSTAIN_AT": v2.PEER_MEDIAN_ABSTAIN_AT,
    }
    assert prereg["scoring"]["scorable"].endswith("(the volume floor both versions share)")
    assert iv.SCORABLE_MIN_LINES == v2.MIN_VISIT_LINES == 40


def test_the_frozen_hashes_match_the_files() -> None:
    prereg_path = iv.PREREG_PATH
    doc = (REPO_ROOT / "docs" / "PROVIDER_INTENSITY_V2_PREREGISTRATION.md").read_text()
    digest = hashlib.sha256(prereg_path.read_bytes()).hexdigest()
    assert digest in doc, "the prose document must carry the frozen hash of the JSON"
    prereg = json.loads(prereg_path.read_text())
    brief = REPO_ROOT / "eval" / "intensity_v2" / "BRIEF_for_author.md"
    assert (
        prereg["data_requirements"]["brief_sha256"]
        == hashlib.sha256(brief.read_bytes()).hexdigest()
    )


def test_the_brief_does_not_leak_detector_constants_or_earlier_results() -> None:
    brief = (REPO_ROOT / "eval" / "intensity_v2" / "BRIEF_for_author.md").read_text().lower()
    for word in (r"binomial", r"bonferroni", r"\bmad\b", r"z-score", r"3\.5", r"0/10", r"p75"):
        assert not re.search(word, brief), word


def test_the_sealed_fixture_files_match_their_recorded_hashes() -> None:
    seal = json.loads((REPO_ROOT / "eval" / "intensity_v2" / "fixture_seal.json").read_text())
    fixture = REPO_ROOT / "eval" / "intensity_v2" / "fixture"
    for name, digest in seal["files_sha256"].items():
        assert iv.sha256_file(fixture / name) == digest, f"{name} changed after sealing"
    assert seal["brief_sha256"] == iv.sha256_file(
        REPO_ROOT / "eval" / "intensity_v2" / "BRIEF_for_author.md"
    )
