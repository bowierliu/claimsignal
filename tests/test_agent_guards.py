"""Structural promises of the agent package: no truth access, no provider calls outside the loop."""

from __future__ import annotations

from pathlib import Path

import pytest

from claims_copilot.agent.prompt import load_prompt
from claims_copilot.budget import load_prices
from claims_copilot.project import BUDGET_DIR, MANIFEST_PATH, REPO_ROOT

AGENT_DIR = REPO_ROOT / "src" / "claims_copilot" / "agent"
TRUTH_TOKENS = (
    "anomaly_truth",
    "truth_claim",
    "truth_line",
    "truth.sqlite",
    "load_dataset",
    "tools.score",
    "import score",
)


def sources() -> list[Path]:
    return sorted(AGENT_DIR.rglob("*.py"))


def test_no_agent_module_reads_the_ground_truth() -> None:
    offenders = [
        f"{p.name}: {t}"
        for p in sources()
        for t in TRUTH_TOKENS
        if t in p.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_only_the_loop_and_adapters_call_the_model_and_only_the_loop_spends() -> None:
    """Adapters define `complete`; the loop is the one caller and wraps it in CostGuard."""
    callers = [p.name for p in sources() if ".complete(" in p.read_text(encoding="utf-8")]
    assert callers == []  # the loop passes the bound method to CostGuard.call instead
    loop = (AGENT_DIR / "loop.py").read_text(encoding="utf-8")
    assert "self._guard.call(" in loop and "self._provider.complete," in loop
    for adapter in (AGENT_DIR / "providers").glob("*.py"):
        text = adapter.read_text(encoding="utf-8")
        assert "import CostGuard" not in text and "default_guard" not in text


def test_library_modules_do_not_print() -> None:
    for path in sources():
        if path.name in ("smoke.py", "__main__.py"):
            continue
        assert "print(" not in path.read_text(encoding="utf-8"), path.name


def test_the_runtime_prompt_loads_and_has_the_required_sections() -> None:
    prompt = load_prompt("agent_v1")
    assert prompt.version == "agent_v1" and len(prompt.sha256) == 64
    for heading in ("# Role", "# Context", "# Inputs", "# Constraints", "# Output", "# Examples"):
        assert heading in prompt.text
    assert "# Failure behaviour" in prompt.text


def test_prompt_versions_cannot_escape_the_prompt_directory() -> None:
    with pytest.raises(ValueError):
        load_prompt("../README")


def test_agent_models_have_verified_prices_with_manifest_sources() -> None:
    import json

    prices = load_prices(BUDGET_DIR / "prices.toml")
    manifest = {
        json.loads(line)["source_id"]: json.loads(line)
        for line in MANIFEST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    for key in ("openai/gpt-6-luna", "anthropic/claude-haiku-5-5"):
        price = prices[key]
        assert manifest[price.source_id]["status"] == "VERIFIED"
