#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCENARIO="${1:-golden}"
shift || true
case "$SCENARIO" in
  golden|rogue-runway) exec bash "$SCRIPT_DIR/golden/run.sh" "$@" ;;
  false-positive)
    echo "Scenario spec: $SCRIPT_DIR/false-positive/timeline.yaml"
    echo "Starting shared Bordeaux stack; false-positive classification/disposition driver is a separate acceptance path."
    exec bash "$SCRIPT_DIR/golden/run.sh" "$@" ;;
  degraded|degraded-localization)
    echo "Scenario spec: $SCRIPT_DIR/degraded-localization/timeline.yaml"
    echo "Starting shared Bordeaux stack; degraded localization timeline drives sensor-loss/restoration acceptance."
    exec bash "$SCRIPT_DIR/golden/run.sh" "$@" ;;
  --doctor) exec bash "$SCRIPT_DIR/golden/doctor.sh" ;;
  *)
    echo "Usage: demo/run.sh [golden|rogue-runway|false-positive|degraded-localization] [options]" >&2
    exit 2
    ;;
esac
