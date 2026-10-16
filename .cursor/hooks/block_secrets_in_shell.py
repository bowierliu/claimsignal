"""Cursor beforeShellExecution hook: deny shell commands that contain credentials.

Reads the hook payload (JSON) on stdin and writes a permission decision (JSON) on stdout.
Stdlib only. Never echoes the matched text back, so a blocked secret does not leak into logs.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "openai_or_anthropic_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "github_token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,})"),
    "aws_access_key_id": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private_key_block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "credential_in_url": re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s@'\"]+@", re.IGNORECASE),
    "literal_secret_assignment": re.compile(
        r"\b(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|NCBI_API_KEY|GITHUB_TOKEN|GH_TOKEN)"
        r"\s*=['\"]?(?!\$)[^\s'\"]{8,}"
    ),
}


def find_secret_kinds(text: str) -> list[str]:
    return [kind for kind, pattern in SECRET_PATTERNS.items() if pattern.search(text)]


def decide(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict) or not isinstance(payload.get("command"), str):
        return {
            "permission": "deny",
            "user_message": "Secret-scan hook received an unexpected payload; blocked.",
            "agent_message": "Shell command blocked: hook payload was malformed.",
        }
    kinds = find_secret_kinds(payload["command"])
    if not kinds:
        return {"permission": "allow"}
    summary = ", ".join(kinds)
    return {
        "permission": "deny",
        "user_message": f"Blocked a shell command that appears to contain a credential: {summary}",
        "agent_message": (
            f"Shell command blocked: it appears to contain a credential ({summary}). "
            "Read secrets from .env or environment variables; never inline them in commands."
        ),
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = None
    json.dump(decide(payload), sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
