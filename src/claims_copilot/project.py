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
CATALOG_PATH = SOURCES_DIR / "catalog.toml"
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CACHE_DIR = DATA_DIR / "cache"
TEXT_DIR = DATA_DIR / "text"
CHUNKS_DIR = DATA_DIR / "chunks"
INDEX_DIR = DATA_DIR / "index"
SYNTH_DATA_DIR = REPO_ROOT / "src" / "claims_copilot" / "synth" / "data"
ICD_SUBSET_PATH = SYNTH_DATA_DIR / "icd10cm_fy27_subset.txt"
SYNTH_OUT_DIR = DATA_DIR / "synth"
SYNTH_GOLDEN_PATH = REPO_ROOT / "eval" / "synthetic_dataset.json"
