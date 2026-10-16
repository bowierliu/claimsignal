"""Read secrets from the environment or the gitignored .env file, never printing them."""

from __future__ import annotations

import os
from pathlib import Path

from claims_copilot.project import REPO_ROOT


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def get_secret(name: str, env_path: Path = REPO_ROOT / ".env") -> str | None:
    """Return the secret's value, or None if unset or empty. Callers must never log the value."""
    value = os.environ.get(name) or _parse_env_file(env_path).get(name)
    return value or None


def has_secret(name: str, env_path: Path = REPO_ROOT / ".env") -> bool:
    return get_secret(name, env_path) is not None
