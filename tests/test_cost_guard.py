from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from claims_copilot.budget import (
    ApprovalRequiredError,
    BudgetConfigError,
    BudgetExceededError,
    Caps,
    CostGuard,
    Ledger,
    ModelPrice,
    UnknownModelPriceError,
    Usage,
    estimate_tokens,
    load_caps,
    load_prices,
)
from claims_copilot.project import BUDGET_DIR, MANIFEST_PATH

MODEL = "test/embed"


def make_caps(**overrides: object) -> Caps:
    values: dict[str, object] = {
        "total_usd": Decimal("10"),
        "eval_run_usd": Decimal("2"),
        "warn_fraction": Decimal("0.7"),
        "stop_fraction": Decimal("0.9"),
        "phases": {"p0": Decimal("4"), "p1": Decimal("4")},
        "approved_past_stop": frozenset(),
    }
    values.update(overrides)
    return Caps(**values)  # type: ignore[arg-type]


def make_guard(tmp_path: Path, caps: Caps | None = None) -> tuple[CostGuard, list[str]]:
    warnings: list[str] = []
    prices = {
        MODEL: ModelPrice(
            model_key=MODEL,
            input_usd_per_mtok=Decimal("1"),
            output_usd_per_mtok=Decimal("2"),
            source_id="test",
        )
    }
    guard = CostGuard(
        caps or make_caps(),
        prices,
        Ledger(tmp_path / "ledger.jsonl"),
        warn=warnings.append,
        clock=lambda: "2026-01-01T00:00:00+00:00",
    )
    return guard, warnings


def mtok(dollars: str) -> Usage:
    """Usage costing exactly `dollars` at $1 per 1M input tokens."""
    return Usage(input_tokens=int(Decimal(dollars) * 1_000_000), output_tokens=0)


def spend(guard: CostGuard, phase: str, dollars: str, eval_run_id: str | None = None) -> None:
    usage = mtok(dollars)
    guard.call(
        lambda: usage,
        usage_of=lambda u: u,
        phase=phase,
        model_key=MODEL,
        purpose="test",
        estimated_usage=usage,
        eval_run_id=eval_run_id,
    )


def test_cost_uses_input_and_output_prices(tmp_path: Path) -> None:
    guard, _ = make_guard(tmp_path)
    assert guard.cost(MODEL, Usage(1_000_000, 500_000)) == Decimal("2.000000")


def test_unknown_model_is_refused_and_not_logged(tmp_path: Path) -> None:
    guard, _ = make_guard(tmp_path)
    with pytest.raises(UnknownModelPriceError):
        guard.authorize(phase="p0", model_key="nope", purpose="x", estimated_usage=Usage(1, 0))
    assert guard.ledger.entries() == []


def test_unknown_phase_is_rejected(tmp_path: Path) -> None:
    guard, _ = make_guard(tmp_path)
    with pytest.raises(BudgetConfigError):
        guard.authorize(phase="p99", model_key=MODEL, purpose="x", estimated_usage=Usage(1, 0))


def test_call_over_phase_cap_is_refused_before_running(tmp_path: Path) -> None:
    guard, _ = make_guard(tmp_path)
    ran = False

    def fn() -> Usage:
        nonlocal ran
        ran = True
        return Usage(0, 0)

    with pytest.raises(BudgetExceededError):
        guard.call(
            fn,
            usage_of=lambda u: u,
            phase="p0",
            model_key=MODEL,
            purpose="x",
            estimated_usage=mtok("4.01"),
        )
    assert not ran
    assert guard.ledger.entries() == []


def test_total_cap_applies_across_phases(tmp_path: Path) -> None:
    caps = make_caps(
        phases={"p0": Decimal("6"), "p1": Decimal("4")},
        approved_past_stop=frozenset({"total", "phase:p0", "phase:p1"}),
    )
    guard, _ = make_guard(tmp_path, caps)
    spend(guard, "p0", "6")
    spend(guard, "p1", "3.5")
    with pytest.raises(BudgetExceededError, match="total"):
        spend(guard, "p1", "0.6")


def test_eval_run_cap(tmp_path: Path) -> None:
    guard, _ = make_guard(tmp_path)
    spend(guard, "p0", "1", eval_run_id="run-1")
    with pytest.raises(BudgetExceededError, match="eval:run-1"):
        spend(guard, "p0", "1.5", eval_run_id="run-1")
    spend(guard, "p0", "1", eval_run_id="run-2")


def test_warns_at_warn_fraction(tmp_path: Path) -> None:
    guard, warnings = make_guard(tmp_path)
    spend(guard, "p0", "2.7")
    assert warnings == []
    spend(guard, "p0", "0.1")
    assert any("phase:p0" in w and "70%" in w for w in warnings)


def test_stops_at_stop_fraction_until_owner_approves(tmp_path: Path) -> None:
    guard, _ = make_guard(tmp_path)
    spend(guard, "p0", "3.5")
    with pytest.raises(ApprovalRequiredError, match="phase:p0"):
        spend(guard, "p0", "0.1")
    approved, _ = make_guard(tmp_path, make_caps(approved_past_stop=frozenset({"phase:p0"})))
    spend(approved, "p0", "0.1")


def test_failed_call_charges_estimate_and_reraises(tmp_path: Path) -> None:
    guard, _ = make_guard(tmp_path)

    def boom() -> Usage:
        raise ConnectionError("network down")

    with pytest.raises(ConnectionError):
        guard.call(
            boom,
            usage_of=lambda u: u,
            phase="p0",
            model_key=MODEL,
            purpose="x",
            estimated_usage=mtok("0.5"),
        )
    [entry] = guard.ledger.entries()
    assert entry.status == "error"
    assert entry.cost_usd == Decimal("0.5")


def test_successful_call_records_actual_usage(tmp_path: Path) -> None:
    guard, _ = make_guard(tmp_path)
    guard.call(
        lambda: Usage(250_000, 0),
        usage_of=lambda u: u,
        phase="p1",
        model_key=MODEL,
        purpose="embed chunks",
        estimated_usage=Usage(400_000, 0),
    )
    [entry] = guard.ledger.entries()
    assert entry.status == "ok"
    assert entry.estimated_cost_usd == Decimal("0.4")
    assert entry.cost_usd == Decimal("0.25")
    assert guard.ledger.spent(phase="p1") == Decimal("0.25")
    assert guard.ledger.spent(phase="p0") == Decimal(0)


def test_ledger_lines_are_json_with_string_money(tmp_path: Path) -> None:
    guard, _ = make_guard(tmp_path)
    spend(guard, "p0", "0.1")
    row = json.loads((tmp_path / "ledger.jsonl").read_text().strip())
    assert row["cost_usd"] == "0.100000"
    assert row["phase"] == "p0"


@pytest.mark.parametrize(
    "overrides",
    [
        {"warn_fraction": Decimal("0.9"), "stop_fraction": Decimal("0.9")},
        {"phases": {"p0": Decimal("11")}},
        {"eval_run_usd": Decimal("11")},
    ],
)
def test_invalid_caps_are_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(BudgetConfigError):
        make_caps(**overrides)


def test_estimate_tokens_is_conservative() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcdef") == 2
    assert estimate_tokens("a" * 4000) >= 1000


def test_repo_caps_match_owner_approved_budget() -> None:
    caps = load_caps(BUDGET_DIR / "caps.toml")
    assert caps.total_usd == Decimal(50)
    assert caps.eval_run_usd == Decimal(5)
    assert sum(caps.phases.values(), Decimal(0)) == Decimal(40)
    assert caps.approved_past_stop == frozenset()


def test_every_price_cites_a_verified_manifest_source() -> None:
    manifest = {
        row["source_id"]: row
        for row in map(json.loads, MANIFEST_PATH.read_text().splitlines())
        if row
    }
    for price in load_prices(BUDGET_DIR / "prices.toml").values():
        assert price.source_id in manifest, price.model_key
        assert manifest[price.source_id]["status"] == "VERIFIED"
