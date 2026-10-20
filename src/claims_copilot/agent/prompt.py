"""Versioned runtime prompts, stored as files under prompts/."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from claims_copilot.project import PROMPTS_DIR

DEFAULT_PROMPT = "agent_v1"


@dataclass(frozen=True)
class Prompt:
    version: str
    text: str
    sha256: str


def load_prompt(version: str = DEFAULT_PROMPT, directory: Path = PROMPTS_DIR) -> Prompt:
    if not version.replace("_", "").isalnum():
        raise ValueError("prompt version must be letters, digits and underscores")
    text = (directory / f"{version}.md").read_text(encoding="utf-8")
    return Prompt(version, text, hashlib.sha256(text.encode("utf-8")).hexdigest())
