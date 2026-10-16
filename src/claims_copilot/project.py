"""Project identity and repository paths.

PRODUCT_NAME is the single source of truth for the product's display name. User-facing
strings must read it from here rather than hard-coding the name.
"""

from pathlib import Path

PRODUCT_NAME = "claims-copilot"

REPO_ROOT = Path(__file__).resolve().parents[2]
BUDGET_DIR = REPO_ROOT / "budget"
SOURCES_DIR = REPO_ROOT / "SOURCES"
MANIFEST_PATH = SOURCES_DIR / "manifest.jsonl"
