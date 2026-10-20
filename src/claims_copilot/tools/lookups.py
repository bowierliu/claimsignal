"""Exact lookups: claim, member history, provider profile, flag queue.

These return what the database holds and nothing else. No scoring, no ranking.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from claims_copilot.tools.errors import NotFoundError, ToolInputError, check_id, check_limit
from claims_copilot.tools.records import Ref
from claims_copilot.tools.repository import (
    ClaimRow,
    FlagRow,
    LineRow,
    ProviderRow,
    Repository,
)

HISTORY_DEFAULT = 50
QUEUE_DEFAULT = 50


@dataclass(frozen=True)
class ClaimRecord:
    claim: ClaimRow
    lines: tuple[LineRow, ...]
    flags: tuple[FlagRow, ...]

    def refs(self) -> tuple[Ref, ...]:
        return (
            Ref("claim", self.claim.claim_id),
            *(Ref("line", ln.line_id) for ln in self.lines),
        )


@dataclass(frozen=True)
class MemberHistory:
    member_id: str
    claims: tuple[ClaimRow, ...]  # oldest first, at most `limit`
    total_claims: int
    truncated: bool


@dataclass(frozen=True)
class ProviderProfile:
    provider: ProviderRow
    claim_count: int
    line_count: int
    total_billed: Decimal
    flagged_claim_count: int


@dataclass(frozen=True)
class FlagQueue:
    screen_code: str | None
    flags: tuple[FlagRow, ...]
    total: int
    truncated: bool
    next_after: str | None = None  # pass as `after` to get the next page


def get_claim(repo: Repository, claim_id: str) -> ClaimRecord:
    cid = check_id("claim", claim_id)
    return ClaimRecord(
        claim=repo.claim(cid),
        lines=tuple(repo.lines(cid)),
        flags=tuple(repo.flags_for_claim(cid)),
    )


def get_member_history(
    repo: Repository, member_id: str, limit: int = HISTORY_DEFAULT
) -> MemberHistory:
    mid = check_id("member", member_id)
    n = check_limit(limit)
    if not repo.member_exists(mid):
        raise NotFoundError("no such member")
    everything = repo.claims_for("member", mid)
    return MemberHistory(
        member_id=mid,
        claims=tuple(everything[:n]),
        total_claims=len(everything),
        truncated=len(everything) > n,
    )


def get_provider_profile(repo: Repository, provider_id: str) -> ProviderProfile:
    pid = check_id("provider", provider_id)
    provider = repo.provider(pid)
    claims, lines, billed = repo.provider_totals(pid)
    flagged = sum(1 for c in repo.claims_for("provider", pid) if repo.flags_for_claim(c.claim_id))
    return ProviderProfile(provider, claims, lines, billed, flagged)


def get_flags(
    repo: Repository,
    screen_code: str | None = None,
    limit: int = QUEUE_DEFAULT,
    after: str | None = None,
) -> FlagQueue:
    n = check_limit(limit)
    if after is not None:
        check_id("flag", after)
    if screen_code is not None and not (
        isinstance(screen_code, str) and screen_code.startswith("SCR") and len(screen_code) == 5
    ):
        raise ToolInputError("screen_code must look like 'SCR01'")
    total = repo.count_flags(screen_code)
    flags = tuple(repo.flag_queue(screen_code, n + 1, after))  # one extra row shows another page
    more = len(flags) > n
    flags = flags[:n]
    return FlagQueue(
        screen_code=screen_code,
        flags=flags,
        total=total,
        truncated=more,
        next_after=flags[-1].flag_id if more else None,
    )
