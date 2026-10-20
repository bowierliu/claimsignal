"""Tool input errors. Messages never echo long or unexpected input."""

from __future__ import annotations

import re

_PATTERNS = {
    "claim": re.compile(r"C[0-9]{7}"),
    "member": re.compile(r"M[0-9]{6}"),
    "provider": re.compile(r"P[0-9]{4}"),
    "flag": re.compile(r"F[0-9]{6}"),
}
SCREEN_CODE_PATTERN = r"SCR[0-9]{2}"
_SHOWN = 16


class ToolInputError(ValueError):
    """The caller passed an argument that is not a well-formed id or value."""


class NotFoundError(LookupError):
    """The id is well formed but no such row exists."""


def _shown(value: object) -> str:
    text = str(value)
    return text if len(text) <= _SHOWN else text[:_SHOWN] + "..."


def id_regex(kind: str) -> str:
    """The anchored pattern for ids of `kind`, for the API to publish in its schema."""
    return f"^{_PATTERNS[kind].pattern}$"


def check_id(kind: str, value: object) -> str:
    """Return `value` if it is a well-formed id of `kind`; otherwise raise ToolInputError."""
    if not isinstance(value, str) or not _PATTERNS[kind].fullmatch(value):
        raise ToolInputError(f"not a valid {kind} id: {_shown(value)!r}")
    return value


def check_limit(value: object, *, maximum: int = 200) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= maximum:
        raise ToolInputError(f"limit must be an integer from 1 to {maximum}")
    return value
