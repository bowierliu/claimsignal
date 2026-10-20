"""Request-scope gate: blocks asks for a decision the human must make, before any model call.

Conservative and deterministic. It looks for a request to DETERMINE fraud, denial, payment,
coverage, or medical necessity, not for the bare words, so "what does the manual say about
medical necessity" passes (the post-generation check is the second line). Ambiguous asks may be
blocked; the false-block and miss rates are measured, not assumed (KF entries, Phase 7).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

BLOCK_MESSAGE = (
    "This request asks for a decision (fraud, denial, payment, coverage, or medical necessity). "
    "The copilot does not make those decisions; the investigator does. It can assemble the "
    "evidence for this claim instead: ask what the tools found or what the policy sources say."
)

_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"))
_DETERMINATION = (
    r"(fraud\w*|abus\w*|improper\w*|scam\w*|upcod\w*|"
    r"medically (un)?necessary|payable|covered|eligible)"
)
_VERB = (
    r"(deny|denied|reject|rejected|approve|approved|pay|paid|"
    r"recoup|recouped|refer|referred|pend|pended)"
)
_THING = r"(claim|claims|line|lines|bill|provider)"

BLOCKED_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        # "is this claim fraudulent", "was the billing improper", "is it medically necessary"
        rf"\b(is|was|are|were|does|did)\b(\s+\w+){{0,4}}\s+{_DETERMINATION}\b",
        # "should we deny this", "should I approve", "should this be paid"
        rf"\bshould\b(\s+\w+){{0,4}}\s+(be\s+)?{_VERB}\b",
        # "deny this claim", "approve the claim", "reject that line", "pay this provider"
        rf"\b{_VERB}\s+(this|the|that|these|those)\b(\s+\w+){{0,2}}\s+{_THING}\b",
        # "decide/determine/conclude whether ... fraud / deny / covered"
        rf"\b(decide|determine|conclude|rule|judge|tell me)\b.{{0,60}}"
        rf"\b(deny|denial|{_DETERMINATION})\b",
        # "recommend denying", "advise whether to pay"
        rf"\b(recommend|advise|suggest)\b.{{0,40}}\b{_VERB}\w*\b",
        # "give me a verdict / decision", "yes or no"
        r"\b(verdict|final decision|yes or no)\b",
        # "is there fraud", "does this show fraud", "prove fraud"
        r"\b(is there|are there|any|show(s)?|prove[sd]?|confirm(s)?)\b(\s+\w+){0,3}\s+fraud\w*\b",
    )
)


@dataclass(frozen=True)
class ScopeDecision:
    blocked: bool
    matched: str | None = None


def normalise(text: str) -> str:
    """Fold look-alike characters, drop invisible ones, lowercase, collapse whitespace."""
    folded = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH)
    return re.sub(r"\s+", " ", folded).strip().lower()


def check_request(question: str) -> ScopeDecision:
    text = normalise(question)
    for pattern in BLOCKED_PATTERNS:
        match = pattern.search(text)
        if match:
            return ScopeDecision(True, match.group(0)[:80])
    return ScopeDecision(False)
