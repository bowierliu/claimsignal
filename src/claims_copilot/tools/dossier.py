"""One call that runs the checks that apply to a claim and returns everything, unranked.

The order is fixed and carries no meaning. The dossier does not combine findings into a score,
a priority, or a recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass

from claims_copilot.tools.codes import validate_claim_codes
from claims_copilot.tools.duplicates import find_duplicate_candidates
from claims_copilot.tools.edits import check_bundling, check_service_dates, check_unit_limits
from claims_copilot.tools.icd import IcdCodeSet
from claims_copilot.tools.lookups import ClaimRecord, get_claim
from claims_copilot.tools.patterns import PeerBook, provider_intensity
from claims_copilot.tools.records import ToolResult
from claims_copilot.tools.repository import Repository
from claims_copilot.tools.rules import RulesProvider


@dataclass(frozen=True)
class Dossier:
    record: ClaimRecord
    results: tuple[ToolResult, ...]

    def finding_count(self) -> int:
        return sum(len(r.findings) for r in self.results)


def claim_dossier(
    repo: Repository,
    rules: RulesProvider,
    claim_id: str,
    icd: IcdCodeSet | None = None,
    book: PeerBook | None = None,
) -> Dossier:
    record = get_claim(repo, claim_id)
    cid = record.claim.claim_id
    results = (
        check_bundling(repo, rules, cid),
        check_unit_limits(repo, rules, cid),
        check_service_dates(repo, cid),
        find_duplicate_candidates(repo, cid),
        validate_claim_codes(repo, cid, icd),
        provider_intensity(repo, record.claim.provider_id, book),
    )
    return Dossier(record=record, results=results)
