"""Edit checks on one claim: bundle pairs, unit limits, service dates.

Each check states a data fact ("component code billed on the same claim and date as its
comprehensive code, without the exception modifier"). None of them says why, or what to do. The
rules are the invented synthetic ones behind `RulesProvider`, not NCCI or MUE.
"""

from __future__ import annotations

from claims_copilot.tools.errors import check_id
from claims_copilot.tools.records import Finding, Ref, ToolResult
from claims_copilot.tools.repository import Repository
from claims_copilot.tools.rules import RulesProvider

BUNDLE_CHECK = "bundle_pair_without_exception"
UNIT_CHECK = "units_above_line_limit"
DATE_CHECK = "line_date_outside_claim_window"
WINDOW_CHECK = "claim_window_reversed"


def check_bundling(repo: Repository, rules: RulesProvider, claim_id: str) -> ToolResult:
    cid = check_id("claim", claim_id)
    repo.claim(cid)
    lines = repo.lines(cid)
    findings: list[Finding] = []
    observations: list[Finding] = []
    pairs_present = 0
    for rule in rules.bundle_rules():
        comps = [ln for ln in lines if ln.code == rule.component_code]
        for comp in comps:
            same_day = [
                ln
                for ln in lines
                if ln.code == rule.comprehensive_code and ln.service_date == comp.service_date
            ]
            if not same_day:
                continue
            pairs_present += 1
            refs = (
                Ref("claim", cid),
                Ref("line", comp.line_id),
                *(Ref("line", ln.line_id) for ln in same_day),
                Ref("rule", rule.rule_id),
            )
            detail = (
                ("comprehensive_code", rule.comprehensive_code),
                ("component_code", rule.component_code),
                ("service_date", comp.service_date.isoformat()),
                ("exception_modifier", rule.exception_modifier),
                ("component_modifiers", ",".join(comp.modifiers) or "none"),
            )
            if rule.exception_modifier in comp.modifiers:
                observations.append(
                    Finding(
                        "bundle_pair_with_exception",
                        f"{rule.component_code} billed with {rule.comprehensive_code} on "
                        f"{comp.service_date}, and carries exception modifier "
                        f"{rule.exception_modifier}; the rule is not tripped.",
                        refs,
                        detail,
                    )
                )
            else:
                findings.append(
                    Finding(
                        BUNDLE_CHECK,
                        f"{rule.component_code} is billed on the same claim and date "
                        f"({comp.service_date}) as {rule.comprehensive_code} without exception "
                        f"modifier {rule.exception_modifier}.",
                        refs,
                        detail,
                    )
                )
    return ToolResult(
        tool="check_bundling",
        subject=cid,
        examined=(
            f"{len(lines)} lines against {len(rules.bundle_rules())} bundle pairs; "
            f"{pairs_present} pair occurrences on a shared date"
        ),
        findings=tuple(findings),
        observations=tuple(observations),
        parameters=(("ruleset", rules.name),),
        limits=("Bundle pairs are checked within one claim and one service date only.",),
    )


def check_unit_limits(repo: Repository, rules: RulesProvider, claim_id: str) -> ToolResult:
    cid = check_id("claim", claim_id)
    repo.claim(cid)
    lines = repo.lines(cid)
    limits = rules.unit_rules()
    findings: list[Finding] = []
    no_limit = 0
    for ln in lines:
        rule = limits.get(ln.code)
        if rule is None:
            no_limit += 1
            continue
        if ln.units > rule.max_units:
            findings.append(
                Finding(
                    UNIT_CHECK,
                    f"Line {ln.line_no} bills {ln.units} units of {ln.code}; the per-line "
                    f"limit is {rule.max_units}.",
                    (Ref("claim", cid), Ref("line", ln.line_id), Ref("rule", rule.rule_id)),
                    (
                        ("code", ln.code),
                        ("units", str(ln.units)),
                        ("max_units", str(rule.max_units)),
                        ("over_by", str(ln.units - rule.max_units)),
                    ),
                )
            )
    return ToolResult(
        tool="check_unit_limits",
        subject=cid,
        examined=f"{len(lines)} lines; {len(lines) - no_limit} have a unit limit",
        findings=tuple(findings),
        parameters=(("ruleset", rules.name),),
        limits=(
            "The limit applies to a single line. Units summed across lines or days are not "
            "checked.",
        ),
    )


def check_service_dates(repo: Repository, claim_id: str) -> ToolResult:
    cid = check_id("claim", claim_id)
    claim = repo.claim(cid)
    lines = repo.lines(cid)
    findings: list[Finding] = []
    if claim.service_to < claim.service_from:
        findings.append(
            Finding(
                WINDOW_CHECK,
                f"Claim service end {claim.service_to} is before its start {claim.service_from}.",
                (Ref("claim", cid),),
                (
                    ("service_from", claim.service_from.isoformat()),
                    ("service_to", claim.service_to.isoformat()),
                ),
            )
        )
    for ln in lines:
        if ln.service_date < claim.service_from:
            days = (claim.service_from - ln.service_date).days
            side = "before"
        elif ln.service_date > claim.service_to:
            days = (ln.service_date - claim.service_to).days
            side = "after"
        else:
            continue
        findings.append(
            Finding(
                DATE_CHECK,
                f"Line {ln.line_no} is dated {ln.service_date}, {days} days {side} the claim "
                f"window {claim.service_from} to {claim.service_to}.",
                (Ref("claim", cid), Ref("line", ln.line_id)),
                (
                    ("line_date", ln.service_date.isoformat()),
                    ("window_from", claim.service_from.isoformat()),
                    ("window_to", claim.service_to.isoformat()),
                    ("days_outside", str(days)),
                    ("side", side),
                ),
            )
        )
    return ToolResult(
        tool="check_service_dates",
        subject=cid,
        examined=(
            f"{len(lines)} line dates against the claim window "
            f"{claim.service_from} to {claim.service_to} (both ends inclusive)"
        ),
        findings=tuple(findings),
        parameters=(("window_bounds", "inclusive"),),
        limits=("Dates are compared with the claim's own window; no external calendar is used.",),
    )
