"""Cost guard for all paid API calls."""

from claims_copilot.budget.config import BudgetConfigError, Caps, ModelPrice, load_caps, load_prices
from claims_copilot.budget.guard import (
    ApprovalRequiredError,
    Authorization,
    BudgetError,
    BudgetExceededError,
    CostGuard,
    UnknownModelPriceError,
    Usage,
    estimate_tokens,
)
from claims_copilot.budget.ledger import Ledger, LedgerEntry
from claims_copilot.project import BUDGET_DIR

__all__ = [
    "ApprovalRequiredError",
    "Authorization",
    "BudgetConfigError",
    "BudgetError",
    "BudgetExceededError",
    "Caps",
    "CostGuard",
    "Ledger",
    "LedgerEntry",
    "ModelPrice",
    "UnknownModelPriceError",
    "Usage",
    "default_guard",
    "estimate_tokens",
    "load_caps",
    "load_prices",
]


def default_guard() -> CostGuard:
    return CostGuard(
        caps=load_caps(BUDGET_DIR / "caps.toml"),
        prices=load_prices(BUDGET_DIR / "prices.toml"),
        ledger=Ledger(BUDGET_DIR / "ledger.jsonl"),
    )
