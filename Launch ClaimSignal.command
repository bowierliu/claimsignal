#!/bin/bash
# Finder launcher. The detached loopback service continues after the Terminal window closes.
set -eu
cd "$(dirname "$0")"
url="http://127.0.0.1:8763"
healthy() { /usr/bin/curl --noproxy '*' -fsS --max-time 1 "$url/api/status" 2>/dev/null | /usr/bin/grep -Fq '"service":"claims-portfolio-v1"'; }
if ! healthy; then
  export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
  if ! command -v uv >/dev/null; then
    echo 'Install uv once using the instructions in README.md, then double-click this launcher again.' >&2
    exit 1
  fi
  uv sync --locked
  # Python starts an independent session and closes inherited terminal handles.
  .venv/bin/python - <<'PY'
from pathlib import Path
import subprocess
import sys
subprocess.Popen(
    [sys.executable, "-m", "claims_copilot.portfolio_server"],
    cwd=Path.cwd(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True,
)
PY
  for attempt in {1..60}; do
    if healthy; then break; fi
    sleep 0.25
  done
  if ! healthy; then
    echo 'The local service could not start. Check whether port 8763 is in use.' >&2
    exit 1
  fi
fi
open "$url"
