"""Budget caps and model prices, loaded from TOML files under budget/."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


class BudgetConfigError(ValueError):
    pass


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise BudgetConfigError(f"{field}: expected a number, got {value!r}")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise BudgetConfigError(f"{field}: not a number: {value!r}") from exc
    if result < 0:
        raise BudgetConfigError(f"{field}: must be non-negative, got {result}")
    return result


@dataclass(frozen=True)
class Caps:
    total_usd: Decimal
    eval_run_usd: Decimal
    warn_fraction: Decimal
    stop_fraction: Decimal
    phases: Mapping[str, Decimal]
    approved_past_stop: frozenset[str]

    def __post_init__(self) -> None:
        if not Decimal(0) < self.warn_fraction < self.stop_fraction < Decimal(1):
            raise BudgetConfigError("require 0 < warn_fraction < stop_fraction < 1")
        allocated = sum(self.phases.values(), Decimal(0))
        if allocated > self.total_usd:
            raise BudgetConfigError(
                f"phase caps sum to ${allocated}, more than total cap ${self.total_usd}"
            )
        if self.eval_run_usd > self.total_usd:
            raise BudgetConfigError("eval_run_usd cannot exceed total_usd")


@dataclass(frozen=True)
class ModelPrice:
    model_key: str
    input_usd_per_mtok: Decimal
    output_usd_per_mtok: Decimal
    source_id: str


def parse_caps(data: Mapping[str, Any]) -> Caps:
    phases_raw = data.get("phases")
    if not isinstance(phases_raw, dict) or not phases_raw:
        raise BudgetConfigError("caps: [phases] table is required")
    approved = data.get("approved_past_stop", [])
    if not isinstance(approved, list) or not all(isinstance(s, str) for s in approved):
        raise BudgetConfigError("caps: approved_past_stop must be a list of strings")
    return Caps(
        total_usd=_decimal(data.get("total_usd"), "total_usd"),
        eval_run_usd=_decimal(data.get("eval_run_usd"), "eval_run_usd"),
        warn_fraction=_decimal(data.get("warn_fraction"), "warn_fraction"),
        stop_fraction=_decimal(data.get("stop_fraction"), "stop_fraction"),
        phases={str(k): _decimal(v, f"phases.{k}") for k, v in phases_raw.items()},
        approved_past_stop=frozenset(approved),
    )


def parse_prices(data: Mapping[str, Any]) -> dict[str, ModelPrice]:
    models = data.get("models")
    if not isinstance(models, dict):
        raise BudgetConfigError("prices: [models] table is required")
    prices: dict[str, ModelPrice] = {}
    for key, row in models.items():
        if not isinstance(row, dict):
            raise BudgetConfigError(f"prices: models.{key} must be a table")
        source_id = row.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise BudgetConfigError(f"prices: models.{key} needs a source_id")
        prices[key] = ModelPrice(
            model_key=key,
            input_usd_per_mtok=_decimal(row.get("input_usd_per_mtok"), f"{key}.input"),
            output_usd_per_mtok=_decimal(row.get("output_usd_per_mtok"), f"{key}.output"),
            source_id=source_id,
        )
    return prices


def load_caps(path: Path) -> Caps:
    with path.open("rb") as f:
        return parse_caps(tomllib.load(f))


def load_prices(path: Path) -> dict[str, ModelPrice]:
    with path.open("rb") as f:
        return parse_prices(tomllib.load(f))
