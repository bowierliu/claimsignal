"""Cost guard: the only path through which paid API calls may be made.

Every call is priced before it runs, checked against the total, phase, and eval-run caps,
and written to the ledger afterwards. A call that would exceed a cap is refused. Crossing
the warn fraction logs a warning; crossing the stop fraction is refused unless the scope
is listed in caps.approved_past_stop, which only the project owner edits.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TypeVar

from claims_copilot.budget.config import BudgetConfigError, Caps, ModelPrice
from claims_copilot.budget.ledger import CallStatus, Ledger, LedgerEntry

T = TypeVar("T")

_MTOK = Decimal(1_000_000)
_USD_PRECISION = Decimal("0.000001")

logger = logging.getLogger(__name__)


class BudgetError(RuntimeError):
    pass


class UnknownModelPriceError(BudgetError):
    pass


class BudgetExceededError(BudgetError):
    pass


class ApprovalRequiredError(BudgetError):
    pass


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class Authorization:
    phase: str
    model_key: str
    purpose: str
    eval_run_id: str | None
    estimated_usage: Usage
    estimated_cost_usd: Decimal


def estimate_tokens(text: str) -> int:
    """Conservative token estimate: one token per 3 UTF-8 bytes (English averages ~4)."""
    return math.ceil(len(text.encode("utf-8")) / 3)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class CostGuard:
    def __init__(
        self,
        caps: Caps,
        prices: dict[str, ModelPrice],
        ledger: Ledger,
        *,
        warn: Callable[[str], None] | None = None,
        clock: Callable[[], str] = _utc_now,
    ) -> None:
        self.caps = caps
        self.prices = prices
        self.ledger = ledger
        self._warn = warn or logger.warning
        self._clock = clock

    def cost(self, model_key: str, usage: Usage) -> Decimal:
        price = self.prices.get(model_key)
        if price is None:
            raise UnknownModelPriceError(
                f"no verified price for {model_key!r}; add it to budget/prices.toml first"
            )
        if usage.input_tokens < 0 or usage.output_tokens < 0:
            raise ValueError("token counts must be non-negative")
        raw = (
            Decimal(usage.input_tokens) * price.input_usd_per_mtok
            + Decimal(usage.output_tokens) * price.output_usd_per_mtok
        ) / _MTOK
        return raw.quantize(_USD_PRECISION)

    def authorize(
        self,
        *,
        phase: str,
        model_key: str,
        purpose: str,
        estimated_usage: Usage,
        eval_run_id: str | None = None,
    ) -> Authorization:
        if phase not in self.caps.phases:
            raise BudgetConfigError(f"unknown phase {phase!r}; known: {sorted(self.caps.phases)}")
        estimate = self.cost(model_key, estimated_usage)

        scopes: list[tuple[str, Decimal, Decimal]] = [
            ("total", self.caps.total_usd, self.ledger.spent()),
            (f"phase:{phase}", self.caps.phases[phase], self.ledger.spent(phase=phase)),
        ]
        if eval_run_id is not None:
            scopes.append(
                (
                    f"eval:{eval_run_id}",
                    self.caps.eval_run_usd,
                    self.ledger.spent(eval_run_id=eval_run_id),
                )
            )

        for scope, cap, spent in scopes:
            projected = spent + estimate
            if projected > cap:
                raise BudgetExceededError(
                    f"refused: {scope} would reach ${projected} against a ${cap} cap "
                    f"(spent ${spent}, this call ~${estimate})"
                )
        for scope, cap, spent in scopes:
            projected = spent + estimate
            if cap == 0:
                continue
            fraction = projected / cap
            if fraction >= self.caps.stop_fraction and scope not in self.caps.approved_past_stop:
                raise ApprovalRequiredError(
                    f"stopped: {scope} would reach {fraction:.0%} of its ${cap} cap. "
                    f"Owner approval required (add {scope!r} to approved_past_stop)."
                )
            if fraction >= self.caps.warn_fraction:
                self._warn(f"budget warning: {scope} at {fraction:.0%} of its ${cap} cap")

        return Authorization(
            phase=phase,
            model_key=model_key,
            purpose=purpose,
            eval_run_id=eval_run_id,
            estimated_usage=estimated_usage,
            estimated_cost_usd=estimate,
        )

    def record(
        self, auth: Authorization, usage: Usage | None, *, status: CallStatus
    ) -> LedgerEntry:
        """Write the call to the ledger. Without actual usage, the estimate is charged."""
        if usage is None:
            usage, cost = auth.estimated_usage, auth.estimated_cost_usd
        else:
            cost = self.cost(auth.model_key, usage)
        entry = LedgerEntry(
            timestamp=self._clock(),
            phase=auth.phase,
            model_key=auth.model_key,
            purpose=auth.purpose,
            eval_run_id=auth.eval_run_id,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            estimated_cost_usd=auth.estimated_cost_usd,
            cost_usd=cost,
            status=status,
        )
        self.ledger.append(entry)
        return entry

    def call(
        self,
        fn: Callable[[], T],
        *,
        usage_of: Callable[[T], Usage],
        phase: str,
        model_key: str,
        purpose: str,
        estimated_usage: Usage,
        eval_run_id: str | None = None,
    ) -> T:
        auth = self.authorize(
            phase=phase,
            model_key=model_key,
            purpose=purpose,
            estimated_usage=estimated_usage,
            eval_run_id=eval_run_id,
        )
        try:
            result = fn()
        except BaseException:
            self.record(auth, None, status="error")
            raise
        self.record(auth, usage_of(result), status="ok")
        return result
