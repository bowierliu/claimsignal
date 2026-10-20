"""Whole-suite guards: no truth access, no verdict language, tools see only the payer store."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from claims_copilot.synth.config import GeneratorConfig
from claims_copilot.synth.generate import generate
from claims_copilot.synth.store import PAYER_FILE, write_dataset
from claims_copilot.tools.dossier import claim_dossier
from claims_copilot.tools.patterns import PeerBook, provider_peer_group
from claims_copilot.tools.records import Finding, ToolResult
from claims_copilot.tools.repository import Repository
from claims_copilot.tools.rules import SyntheticRules
from tool_fixtures import Db, L, icd_fixture

TOOLS_DIR = Path(__file__).resolve().parents[1] / "src" / "claims_copilot" / "tools"
TRUTH_TOKENS = ("anomaly_truth", "truth_claim", "truth_line", "truth.sqlite", "load_dataset")
VERDICT = re.compile(
    r"\b(fraud\w*|abus\w*|improper\w*|deny|denied|denial|deni\w+|overpa\w+|"
    r"medically necessary|not medically|should (be )?(denied|paid|recouped)|"
    r"recoup\w*|guilty|scheme|intent\w*|illegal|wrongdoing)\b",
    re.IGNORECASE,
)


def test_no_tool_module_reads_the_ground_truth() -> None:
    offenders = []
    for path in sorted(TOOLS_DIR.glob("*.py")):
        if path.name == "score.py":  # the scorecard is the only module allowed to open truth
            continue
        text = path.read_text(encoding="utf-8")
        offenders += [f"{path.name}: {t}" for t in TRUTH_TOKENS if t in text]
    assert offenders == []


def _strings(result: ToolResult) -> list[str]:
    out = [result.tool, result.subject, result.examined, *result.limits]
    for f in (*result.findings, *result.observations):
        out += [f.check, f.summary, *(k for k, _ in f.detail), *(v for _, v in f.detail)]
    out += [k for k, _ in result.parameters] + [v for _, v in result.parameters]
    out += [k for k, _ in result.metrics] + [v for _, v in result.metrics]
    return out


def test_verdict_words_are_detected_by_the_scan() -> None:
    assert VERDICT.search("this looks like fraud")
    assert VERDICT.search("claim should be denied")
    assert not VERDICT.search("component code billed without exception modifier")


def test_findings_never_use_verdict_language_on_generated_data(tmp_path: Path) -> None:
    ds = generate(GeneratorConfig.small())
    write_dataset(ds, tmp_path)
    repo = Repository.open(tmp_path / PAYER_FILE)
    rules = SyntheticRules(repo)
    book = PeerBook.from_repo(repo)
    icd = icd_fixture(*{c for cl in ds.claims for c in cl.diagnosis_codes})
    flagged = sorted({f.claim_id for f in ds.flags})
    assert flagged
    scanned = 0
    for cid in flagged:
        dossier = claim_dossier(repo, rules, cid, icd, book)
        assert len(dossier.results) == 6
        for res in dossier.results:
            for text in _strings(res):
                assert not VERDICT.search(text), (cid, text)
            scanned += 1
    for pid in {c.provider_id for c in ds.claims if c.claim_id in flagged[:20]}:
        rep = provider_peer_group(repo, pid, book)
        assert not VERDICT.search(" ".join(rep.limits))
    assert scanned >= len(flagged) * 6


def test_the_dossier_lists_results_without_ranking_or_a_score(tmp_path: Path) -> None:
    db = Db(tmp_path / "p.sqlite")
    db.claim("C0000001", [L("X0010"), L("X0011"), L("X0020", units=5)])
    repo = db.open()
    dossier = claim_dossier(repo, SyntheticRules(repo), "C0000001", icd_fixture("E119"))
    assert [r.tool for r in dossier.results] == [
        "check_bundling",
        "check_unit_limits",
        "check_service_dates",
        "find_duplicate_candidates",
        "validate_claim_codes",
        "provider_intensity",
    ]
    assert dossier.finding_count() == 2
    names = {f for f in dir(dossier) if not f.startswith("_")}
    assert not {n for n in names if "score" in n or "rank" in n or "priority" in n}
    assert isinstance(dossier.results[0].findings[0], Finding)


def test_every_empty_result_still_says_what_was_examined(tmp_path: Path) -> None:
    db = Db(tmp_path / "p.sqlite")
    db.claim("C0000001", [L("X0001")])
    repo = db.open()
    dossier = claim_dossier(repo, SyntheticRules(repo), "C0000001", None)
    for res in dossier.results:
        assert res.examined.strip(), res.tool
    assert any("not checked" in s for r in dossier.results for s in r.limits)


@pytest.mark.parametrize("bad", ["C1", "C0000001'--", "", "../C0000001"])
def test_dossier_rejects_malformed_ids(tmp_path: Path, bad: str) -> None:
    db = Db(tmp_path / "p.sqlite")
    db.claim("C0000001", [L("X0001")])
    repo = db.open()
    from claims_copilot.tools.errors import ToolInputError

    with pytest.raises(ToolInputError):
        claim_dossier(repo, SyntheticRules(repo), bad)
