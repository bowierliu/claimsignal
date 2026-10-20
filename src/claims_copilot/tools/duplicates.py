"""Duplicate candidates for one claim.

Two tiers, kept apart so the investigator sees how strong each match is:

- `exact_duplicate`: same member, same provider, same service window, and the same multiset of
  lines (code, modifiers, units). This is the tier a screen would count as a duplicate.
- `near_match_*`: looser matches that are often legitimate (a repeat visit, a second provider).
  They are shown as observations and never as findings.

Near-match settings are this project's invention; the window is a parameter and the scorecard
measures how often the near tiers fire on claims that are fine.
"""

from __future__ import annotations

from datetime import date

from claims_copilot.tools.errors import check_id
from claims_copilot.tools.records import Finding, Ref, ToolResult
from claims_copilot.tools.repository import ClaimRow, LineRow, Repository

EXACT_CHECK = "exact_duplicate"
NEAR_PROVIDER = "near_match_other_provider"
NEAR_DATE = "near_match_nearby_date"
NEAR_DAYS = 30

Signature = tuple[tuple[str, tuple[str, ...], int], ...]


def line_signature(lines: list[LineRow]) -> Signature:
    return tuple(sorted((ln.code, ln.modifiers, ln.units) for ln in lines))


def _overlap(a: ClaimRow, b: ClaimRow) -> bool:
    return a.service_from <= b.service_to and b.service_from <= a.service_to


def find_duplicate_candidates(
    repo: Repository, claim_id: str, near_days: int = NEAR_DAYS
) -> ToolResult:
    cid = check_id("claim", claim_id)
    claim = repo.claim(cid)
    member_claims = repo.claims_for("member", claim.member_id)
    lines_by_claim = repo.member_lines(claim.member_id)
    mine = line_signature(lines_by_claim.get(cid, []))
    findings: list[Finding] = []
    observations: list[Finding] = []
    others = [c for c in member_claims if c.claim_id != cid]
    for other in others:
        theirs = line_signature(lines_by_claim.get(other.claim_id, []))
        if theirs != mine or not mine:
            continue
        refs = (Ref("claim", cid), Ref("claim", other.claim_id), Ref("member", claim.member_id))
        detail = (
            ("this_claim", cid),
            ("other_claim", other.claim_id),
            ("this_provider", claim.provider_id),
            ("other_provider", other.provider_id),
            ("this_window", f"{claim.service_from}..{claim.service_to}"),
            ("other_window", f"{other.service_from}..{other.service_to}"),
            ("line_count", str(len(mine))),
        )
        if (
            other.provider_id == claim.provider_id
            and other.service_from == claim.service_from
            and other.service_to == claim.service_to
        ):
            findings.append(
                Finding(
                    EXACT_CHECK,
                    f"Claim {other.claim_id} has the same member, provider, service window and "
                    f"{len(mine)} identical lines (code, modifiers, units) as {cid}.",
                    refs,
                    detail,
                )
            )
        elif other.provider_id != claim.provider_id and _overlap(claim, other):
            observations.append(
                Finding(
                    NEAR_PROVIDER,
                    f"Claim {other.claim_id} from provider {other.provider_id} has identical "
                    f"lines and an overlapping service window.",
                    refs,
                    detail,
                )
            )
        elif other.provider_id == claim.provider_id and _gap(claim, other) <= near_days:
            observations.append(
                Finding(
                    NEAR_DATE,
                    f"Claim {other.claim_id} from the same provider has identical lines "
                    f"{_gap(claim, other)} days away.",
                    refs,
                    detail,
                )
            )
    return ToolResult(
        tool="find_duplicate_candidates",
        subject=cid,
        examined=(
            f"{len(others)} other claims for member {claim.member_id}; compared the multiset of "
            f"(code, modifiers, units) per claim"
        ),
        findings=tuple(findings),
        observations=tuple(observations),
        parameters=(("near_match_days", str(near_days)),),
        limits=(
            "Only the same member's claims are compared. Diagnoses and amounts are not part of "
            "the match.",
            "Near matches are shown for context; many are ordinary repeat services.",
        ),
    )


def _gap(a: ClaimRow, b: ClaimRow) -> int:
    first: date = min(a.service_from, b.service_from)
    last: date = max(a.service_from, b.service_from)
    return (last - first).days
