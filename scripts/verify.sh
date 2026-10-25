#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
exec /usr/bin/python3 src/pd_drone/verify_live.py "$@"
