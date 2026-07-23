#!/usr/bin/env bash
set -euo pipefail
# Bundle golden demo logs and acceptance report into a timestamped archive.

LOG_DIR="${GOLDEN_LOG_DIR:-${TMPDIR:-/tmp}/furia-bod-golden}"
BUNDLE_DIR="${GOLDEN_BUNDLE_DIR:-/tmp/furia-bod-golden-bundles}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BUNDLE_NAME="furia-bod-golden-$TIMESTAMP"
BUNDLE_PATH="$BUNDLE_DIR/$BUNDLE_NAME"

mkdir -p "$BUNDLE_DIR"

# Copy logs
mkdir -p "$BUNDLE_PATH/logs"
if [[ -d "$LOG_DIR" ]]; then
  cp -r "$LOG_DIR/" "$BUNDLE_PATH/logs/"
fi

# Generate acceptance report
python3 "$(dirname "$0")/acceptance_report.py" > "$BUNDLE_PATH/acceptance.json" 2>&1 || true

# Generate summary
{
  echo "Bordeaux C-UAS Golden Demo — $TIMESTAMP"
  echo ""
  echo "=== Verifier Results ==="
  for log in "$BUNDLE_PATH/logs"/verify*.log; do
    if [[ -f "$log" ]]; then
      name=$(basename "$log")
      if grep -q "PASS" "$log"; then
        echo "  ✅ $name: PASS"
      elif grep -q "FAIL" "$log"; then
        echo "  ❌ $name: FAIL"
      else
        echo "  ⚠️  $name: no result"
      fi
    fi
  done
  echo ""
  if [[ -f "$BUNDLE_PATH/acceptance.json" ]]; then
    echo "=== Acceptance Report ==="
    cat "$BUNDLE_PATH/acceptance.json"
  fi
} > "$BUNDLE_PATH/summary.txt"

# Create archive
cd "$BUNDLE_DIR"
tar czf "$BUNDLE_NAME.tar.gz" "$BUNDLE_NAME"
echo "Bundle: $BUNDLE_DIR/$BUNDLE_NAME.tar.gz"
echo "Summary: $BUNDLE_PATH/summary.txt"