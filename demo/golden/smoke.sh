#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export GOLDEN_EXIT_AFTER_ACCEPTANCE=1
export DEMO_SPEED="${DEMO_SPEED:-8.0}"
exec bash "$SCRIPT_DIR/run.sh"
