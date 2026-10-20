"""Write or check the committed OpenAPI document: `python -m claims_copilot.api.snapshot [--check]`.

The snapshot is the API contract. A test compares it with the live schema, so a change to a route
or model shows up as a reviewable diff of `docs/openapi.json`.
"""

from __future__ import annotations

import json
import sys

from claims_copilot.api.app import app_without_data
from claims_copilot.project import REPO_ROOT

SNAPSHOT_PATH = REPO_ROOT / "docs" / "openapi.json"


def render() -> str:
    return json.dumps(app_without_data().openapi(), indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    text = render()
    if "--check" in args:
        same = SNAPSHOT_PATH.is_file() and SNAPSHOT_PATH.read_text(encoding="utf-8") == text
        print("openapi snapshot is current" if same else "openapi snapshot is STALE")
        return 0 if same else 1
    SNAPSHOT_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {SNAPSHOT_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
