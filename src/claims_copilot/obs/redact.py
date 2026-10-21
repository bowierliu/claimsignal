"""Find and mask sensitive strings before they reach a log, a trace, or an audit entry.

All project data is synthetic, so this is defence in depth, not a claim that real PHI is handled:
a deployment on real data needs a reviewed scanner. The patterns cover US social security numbers,
phone numbers, email addresses, and the common shapes of credentials (provider keys, cloud keys,
bearer tokens, private-key headers, `name=value` secrets). A match is replaced by `[REDACTED:kind]`
so the surrounding text stays useful. The scanner never returns or logs the matched text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

PATTERNS: dict[str, re.Pattern[str]] = {
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "provider_key": re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}"),
    "cloud_key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "token": re.compile(r"\b(?:ghp|gho|ghs|github_pat)_[A-Za-z0-9_]{20,}"),
    "bearer": re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    "named_secret": re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*[\"']?[^\s\"',;]{8,}"
    ),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone": re.compile(r"(?<!\d)(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}(?!\d)"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
}


@dataclass(frozen=True)
class Finding:
    kind: str
    start: int
    end: int


def scan(text: str) -> list[Finding]:
    """Every sensitive match, by kind and position. The matched text is not kept."""
    found = [Finding(k, m.start(), m.end()) for k, p in PATTERNS.items() for m in p.finditer(text)]
    return sorted(found, key=lambda f: (f.start, f.end))


def redact(text: str) -> str:
    """The text with every match replaced; overlapping matches are merged, earliest kind wins."""
    out: list[str] = []
    cursor = 0
    for f in scan(text):
        if f.start < cursor:
            continue
        out.append(text[cursor : f.start])
        out.append(f"[REDACTED:{f.kind}]")
        cursor = f.end
    out.append(text[cursor:])
    return "".join(out)


def kinds(text: str) -> list[str]:
    return sorted({f.kind for f in scan(text)})
