"""Code validation for one claim.

Procedure codes are checked against the synthetic code table. Diagnosis codes are checked against
the FY2027 ICD-10-CM billable list (`IcdCodeSet`), only when that list is available and the
claim's service dates fall in its fiscal year. If either is missing, the result says "not
checked" in `limits`; it never guesses and never falls back to a partial list.
"""

from __future__ import annotations

from claims_copilot.tools.errors import check_id
from claims_copilot.tools.icd import IcdCodeSet, normalize_code
from claims_copilot.tools.records import Finding, Ref, ToolResult
from claims_copilot.tools.repository import Repository

UNKNOWN_PROC = "procedure_code_not_in_table"
UNKNOWN_DX = "diagnosis_code_not_in_code_set"
BAD_POINTER = "diagnosis_pointer_out_of_range"
NO_DX = "claim_has_no_diagnosis"
DUPLICATE_DX = "diagnosis_code_repeated"
OUT_OF_SET_YEAR = "service_dates_outside_code_set_year"


def validate_claim_codes(
    repo: Repository, claim_id: str, icd: IcdCodeSet | None = None
) -> ToolResult:
    cid = check_id("claim", claim_id)
    claim = repo.claim(cid)
    lines = repo.lines(cid)
    procedures = repo.procedure_codes()
    findings: list[Finding] = []
    limits: list[str] = []
    for ln in lines:
        if ln.code not in procedures:
            findings.append(
                Finding(
                    UNKNOWN_PROC,
                    f"Line {ln.line_no} uses procedure code {ln.code}, which is not in the code "
                    f"table.",
                    (Ref("claim", cid), Ref("line", ln.line_id)),
                    (("code", ln.code),),
                )
            )
        if not 1 <= ln.dx_pointer <= len(claim.diagnosis_codes):
            findings.append(
                Finding(
                    BAD_POINTER,
                    f"Line {ln.line_no} points to diagnosis {ln.dx_pointer}, but the claim has "
                    f"{len(claim.diagnosis_codes)}.",
                    (Ref("claim", cid), Ref("line", ln.line_id)),
                    (
                        ("dx_pointer", str(ln.dx_pointer)),
                        ("diagnosis_count", str(len(claim.diagnosis_codes))),
                    ),
                )
            )
    if not claim.diagnosis_codes:
        findings.append(Finding(NO_DX, "The claim lists no diagnosis codes.", (Ref("claim", cid),)))
    seen: set[str] = set()
    for code in claim.diagnosis_codes:
        if normalize_code(code) in seen:
            findings.append(
                Finding(
                    DUPLICATE_DX,
                    f"Diagnosis code {code} appears more than once on the claim.",
                    (Ref("claim", cid),),
                    (("code", code),),
                )
            )
        seen.add(normalize_code(code))
    dx_checked = 0
    if icd is None:
        limits.append("Diagnosis codes were not checked: the ICD-10-CM code list is unavailable.")
    elif not (icd.covers(claim.service_from) and icd.covers(claim.service_to)):
        findings.append(
            Finding(
                OUT_OF_SET_YEAR,
                f"Service dates {claim.service_from} to {claim.service_to} are outside the "
                f"{icd.name} period ({icd.valid_from} to {icd.valid_to}); diagnosis codes could "
                f"not be validated.",
                (Ref("claim", cid),),
                (("code_set", icd.name),),
            )
        )
        limits.append("Diagnosis codes were not checked against a code set in effect.")
    else:
        for code in claim.diagnosis_codes:
            dx_checked += 1
            if not icd.contains(code):
                findings.append(
                    Finding(
                        UNKNOWN_DX,
                        f"Diagnosis code {code} is not a billable code in the {icd.name}.",
                        (Ref("claim", cid),),
                        (("code", code), ("code_set", icd.name)),
                    )
                )
    return ToolResult(
        tool="validate_claim_codes",
        subject=cid,
        examined=(
            f"{len(lines)} procedure codes against the code table; {dx_checked} of "
            f"{len(claim.diagnosis_codes)} diagnosis codes against the ICD-10-CM list"
        ),
        findings=tuple(findings),
        parameters=(("diagnosis_code_set", icd.name if icd else "unavailable"),),
        limits=tuple(limits),
    )
