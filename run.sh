#!/usr/bin/env sh
# Launch Wind Waker HD. Everything else lives in Python; keep this a shim.
set -eu
cd "$(dirname "$0")"
exec uv run --frozen python bootstrap.py "$@"
