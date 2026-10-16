"""Guards the Cursor configuration and the records the working agreement promises exist."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from claims_copilot.project import REPO_ROOT

RECORDS = [
    "README.md",
    "AGENTS.md",
    "DECISIONS.md",
    "EVALUATION.md",
    "KNOWN_FAILURES.md",
    "ANSWER_BOUNDARY.md",
    "DATA_MODEL.md",
    "ROADMAP.md",
    "SESSION_LOG.md",
    "RESUME_METRICS.md",
    "docs/ARCHITECTURE.md",
]
LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


def frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines and lines[0] == "---", f"{path} must start with YAML frontmatter"
    end = lines.index("---", 1)
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip("\"'")
    return fields


@pytest.mark.parametrize("name", RECORDS)
def test_record_exists_and_is_not_empty(name: str) -> None:
    assert (REPO_ROOT / name).read_text(encoding="utf-8").strip()


@pytest.mark.parametrize("name", RECORDS)
def test_local_markdown_links_resolve(name: str) -> None:
    path = REPO_ROOT / name
    for target in LINK.findall(path.read_text(encoding="utf-8")):
        if "://" in target or target.startswith("mailto:"):
            continue
        assert (path.parent / target).exists(), f"{name} links to missing {target}"


def test_skills_have_matching_name_and_description() -> None:
    skills = sorted((REPO_ROOT / ".cursor/skills").glob("*/SKILL.md"))
    names = {p.parent.name for p in skills}
    assert {
        "source-verification",
        "eval-running",
        "decision-logging",
        "cost-guard",
        "phase-report",
        "teach",
    } <= names
    for path in skills:
        meta = frontmatter(path)
        assert meta["name"] == path.parent.name
        assert meta["description"]


def test_teach_and_phase_report_are_explicit_only() -> None:
    for name in ("teach", "phase-report"):
        meta = frontmatter(REPO_ROOT / f".cursor/skills/{name}/SKILL.md")
        assert meta["disable-model-invocation"] == "true"


def test_subagents_are_defined_and_scout_is_read_only() -> None:
    agents = REPO_ROOT / ".cursor/agents"
    scout = frontmatter(agents / "file-scout.md")
    verifier = frontmatter(agents / "source-verifier.md")
    assert scout["readonly"] == "true"
    assert verifier["description"]
    for path in agents.glob("*.md"):
        assert frontmatter(path)["name"] == path.stem


def test_rules_are_mdc_with_scope() -> None:
    rules = sorted((REPO_ROOT / ".cursor/rules").iterdir())
    assert rules, "expected at least one rule"
    for path in rules:
        assert path.suffix == ".mdc", f"{path.name}: Cursor ignores non-.mdc rule files"
        meta = frontmatter(path)
        assert meta["description"]
        assert meta.get("alwaysApply") == "true" or meta.get("globs"), f"{path.name} has no scope"


def test_agents_md_states_every_hard_rule() -> None:
    text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "## Hard rules" in text
    numbered = re.findall(r"^\d+\. ", text.split("## Hard rules")[1].split("##")[0], re.M)
    assert len(numbered) >= 6
    assert "CostGuard" in text
    assert "Definition of done" in text
