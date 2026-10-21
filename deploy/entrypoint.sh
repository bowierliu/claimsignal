#!/bin/sh
# Start the API on the container network. Refuses to start without an API key; never prints it.
set -eu

if [ -z "${CLAIMS_COPILOT_API_KEY:-}" ]; then
    echo "refusing to start: CLAIMS_COPILOT_API_KEY is not set" >&2
    exit 78
fi

exec python -m claims_copilot.api \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --allow-remote \
    --policy-mode lexical
