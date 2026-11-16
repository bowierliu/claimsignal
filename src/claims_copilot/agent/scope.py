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
        # a follow-up command with a pronoun object: "ok, then deny it", "just approve that."
        r"\b(deny|reject|approve|pay|recoup|refer|pend)\s+(it|them|this|that|these|those)"
        r"\s*([.!?,;]|$|\s+(and|then|now|already|anyway|instead|too)\b)",
        # "mark that claim denied", "mark it as approved"
        r"\bmark\b(\s+\w+){0,3}\s+(as\s+)?(denied|approved|paid|rejected|payable|fraudulent)\b",
        # "is the provider committing fraud"
        r"\bcommit(s|ted|ting)?\s+(fraud|abuse)\b",
        # "would you pay this one", "would you deny it"
        r"\bwould you\b(\s+\w+){0,2}\s+(deny|reject|approve|pay|recoup|refer|pend)\s+"
        r"(it|this|that|them|these|those|the|claim)\b",
        # "deny claim C0007073", "approve C0000493"
        rf"\b{_VERB}\s+(claim\s+)?c\d{{7}}\b",
        # a verdict word asked as the question: "... in your view fraudulent?"
        r"\b(fraudulent|abusive|improper|legitimate|upcoding)\W*\?",
        # "classify claim X as legitimate or fraudulent"
        r"\b(classify|categori[sz]e|label)\b.{0,60}\b(legitimate|fraudulent|abusive|improper)\b",
        # "give me your determination on fraud", "your call on payment"
        r"\byour\s+(determination|decision|call|judgment|judgement|ruling)\b",
        # "approve or decline?", "pay or not"
        r"\b(approve|pay|accept)\s+or\s+(decline|deny|reject|not)\b",
    )
)
# Latin look-alikes from Cyrillic and Greek that NFKC leaves alone ("fraud" typed with U+0430).
_CONFUSABLES = str.maketrans(
    "\u0430\u0435\u043e\u0440\u0441\u0443\u0445\u0456\u0455\u0501\u0458\u043d\u0442\u0432\u043c\u043a"
    "\u03bf\u03b1\u03bd\u03c1\u03b5\u03b9\u03ba\u03c4\u03c5",
    "aeopcyxisdjhtbmkoavpeiktu",
)
# Letters split by spaces or punctuation: "d e n y", "f-r-a-u-d", "f.r.a.u.d".
_SPLIT_LETTERS = re.compile(r"\b(?:[a-z][\s\-.*_]){2,}[a-z]\b")


@dataclass(frozen=True)
class ScopeDecision:
    blocked: bool
    matched: str | None = None


def normalise(text: str) -> str:
    """Fold look-alike characters, drop invisible ones, lowercase, collapse whitespace."""
    folded = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH).lower()
    return re.sub(r"\s+", " ", folded.translate(_CONFUSABLES)).strip()


def joined_letters(text: str) -> str:
    return _SPLIT_LETTERS.sub(lambda m: re.sub(r"[\s\-.*_]", "", m.group(0)), text)


def check_request(question: str) -> ScopeDecision:
    text = normalise(question)
    for view in dict.fromkeys((text, joined_letters(text))):
        for pattern in BLOCKED_PATTERNS:
            match = pattern.search(view)
            if match:
                return ScopeDecision(True, match.group(0)[:80])
    return ScopeDecision(False)


def check_followup(question: str, previous: str | None) -> ScopeDecision:
    """Gate a message in a session: alone, and joined to the previous questions, so an ask split
    across turns ("is this claim" / "fraudulent?") is still caught. `previous` is the recent
    unblocked questions joined (`Session.gate_context`). The join counts only when `previous`
    passes on its own; one blocked turn does not block every turn after it."""
    alone = check_request(question)
    if alone.blocked or not previous or check_request(previous).blocked:
        return alone
    return check_request(previous + " " + question)
