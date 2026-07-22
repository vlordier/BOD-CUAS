#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCENARIO="${1:-golden}"
shift || true

case "$SCENARIO" in
  golden|rogue-runway)
    exec bash "$SCRIPT_DIR/golden/run.sh" "$@"
    ;;
  false-positive)
    echo "False-positive scenario specification: $SCRIPT_DIR/false-positive/timeline.yaml"
    echo "Use the standard golden stack, then replay the false-positive timeline through the scenario driver once its classification adapter is enabled."
    exec bash "$SCRIPT_DIR/golden/run.sh" "$@"
    ;;
  degraded|degraded-localization)
    echo "Degraded-localization scenario specification: $SCRIPT_DIR/degraded-localization/timeline.yaml"
    echo "Use the standard golden stack; sensor-loss/restoration events are represented by the degraded localization timeline."
    exec bash "$SCRIPT_DIR/golden/run.sh" "$@"
    ;;
  --doctor)
    exec bash "$SCRIPT_DIR/golden/doctor.sh"
    ;;
  *)
    cat >&2 <<EOF
Usage: demo/run.sh [golden|rogue-runway|false-positive|degraded-localization] [options]

The golden scenario is fully executable and acceptance-checked.
The false-positive and degraded-localization timelines are deterministic scenario specifications sharing the same stack; their specialized classification/sensor-event drivers are intentionally separate from the golden acceptance path.
EOF
    exit 2
    ;;
esac
