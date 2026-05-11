#!/usr/bin/env bash
# run.sh - macOS / Linux launcher for ip-quality-test
# Usage:
#   ./run.sh                                       # test local egress
#   ./run.sh --label jp-01                         # custom label
#   ./run.sh --proxy http://127.0.0.1:6174         # test through a proxy
#   ./run.sh --ip 1.1.1.1 --label cf-dns           # test an arbitrary IP

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "ERROR: Python 3.7+ is required (install via brew install python or apt install python3)." >&2
    exit 2
fi

exec "$PY" "$SCRIPT_DIR/scripts/ip_quality.py" "$@"
