#!/usr/bin/env bash
# Bordeaux C-UAS golden demo — smoke test wrapper.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${TMPDIR:-/tmp}/furia-bod-golden"

echo "=============================================="
echo "  BORDEAUX C-UAS GOLDEN DEMO — SMOKE TEST"
echo "=============================================="
echo ""

# Step 1: Doctor
echo "=== Step 1: Doctor ==="
if ! bash "$SCRIPT_DIR/doctor.sh"; then
    echo "❌ PREREQUISITES FAILED"
    exit 1
fi
echo ""

# Step 2: Run demo
echo "=== Step 2: Run golden demo ==="
GOLDEN_EXIT_AFTER_ACCEPTANCE=1 bash "$SCRIPT_DIR/run.sh"
DEMO_EXIT=$?
echo ""

# Step 3: Check results
echo "=== Step 3: Verify ==="
PASSED=true

if [[ $DEMO_EXIT -ne 0 ]]; then
    echo "  ❌ run.sh exited with code $DEMO_EXIT"
    PASSED=false
fi

for verifier in verify verify_origin verify_comm_denied; do
    log="$LOG_DIR/${verifier}.log"
    if [[ -f "$log" ]]; then
        if grep -q "PASS" "$log"; then
            echo "  ✅ $verifier: PASS"
        elif grep -q "FAIL" "$log"; then
            echo "  ❌ $verifier: FAIL"
            tail -5 "$log"
            PASSED=false
        else
            echo "  ⚠️  $verifier: no result"
            tail -3 "$log"
            PASSED=false
        fi
    else
        echo "  ❌ $verifier: log not found"
        PASSED=false
    fi
done

echo ""
if $PASSED; then
    echo "=============================================="
    echo "  ✅ BORDEAUX C-UAS GOLDEN DEMO: PASS"
    echo "=============================================="
    exit 0
else
    echo "=============================================="
    echo "  ❌ BORDEAUX C-UAS GOLDEN DEMO: FAIL"
    echo "=============================================="
    echo "Logs: $LOG_DIR"
    exit 1
fi