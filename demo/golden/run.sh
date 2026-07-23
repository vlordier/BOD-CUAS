#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${FURIA_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"
CORE="$ROOT/furia-core"
C2="$ROOT/furia-c2"
S1="$ROOT/S1"
LOG_DIR="${TMPDIR:-/tmp}/furia-bod-golden"
mkdir -p "$LOG_DIR"

ALL_PIDS=()
ALL_CONTAINERS=()

cleanup() {
  local rc=$?
  echo "=== Cleaning up ==="
  for pid in "${ALL_PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  for c in "${ALL_CONTAINERS[@]:-}"; do docker rm -f "$c" >/dev/null 2>&1 || true; done
  wait 2>/dev/null || true
  # Remove NATS JetStream store for deterministic re-run
  rm -rf /tmp/furia-bod-nats-js 2>/dev/null || true
  exit "$rc"
}
trap cleanup EXIT INT TERM

wait_http() {
  local url="$1" label="$2" max="${3:-60}" i=0
  until curl -sf "$url" >/dev/null 2>&1; do
    (( i++ >= max )) && { echo "ERROR: $label not ready: $url"; return 1; }
    sleep 1
  done
  printf '%-28s ✅\n' "$label"
}

wait_tcp() {
  local port="$1" label="$2" max="${3:-30}" i=0
  until lsof -i :"$port" 2>/dev/null | grep -q LISTEN; do
    (( i++ >= max )) && { echo "ERROR: $label not ready on :$port"; return 1; }
    sleep 1
  done
  printf '%-28s ✅\n' "$label"
}

wait_log() {
  local log="$1" pattern="$2" label="$3" max="${4:-30}" i=0
  until grep -q "$pattern" "$log" 2>/dev/null; do
    (( i++ >= max )) && { echo "ERROR: $label not ready (no '$pattern' in $log)"; return 1; }
    sleep 1
  done
  printf '%-28s ✅\n' "$label"
}

AUTO_EXIT="${GOLDEN_EXIT_AFTER_ACCEPTANCE:-0}"

if [[ "${1:-}" == "--doctor" ]]; then exec bash "$SCRIPT_DIR/doctor.sh"; fi
bash "$SCRIPT_DIR/doctor.sh"
echo

echo '=== Start NATS JetStream (TCP + WebSocket) ==='
if command -v nats-server >/dev/null 2>&1; then
  nats-server -c "$SCRIPT_DIR/nats.conf" >"$LOG_DIR/nats.log" 2>&1 & ALL_PIDS+=("$!")
else
  name="furia-bod-nats-$$"
  docker run --rm --name "$name" -p 4222:4222 -p 9222:9222 \
    nats:2.10-alpine -js -m 8222 --websocket_port 9222 \
    >"$LOG_DIR/nats.log" 2>&1 &
  ALL_PIDS+=("$!"); ALL_CONTAINERS+=("$name")
fi
wait_tcp 4222 'NATS TCP'
wait_tcp 9222 'NATS WebSocket'
export NATS_URL="${NATS_URL:-nats://127.0.0.1:4222}"
export FURIA_NATS_URL="$NATS_URL"
export UXV_CONFIG_DIR="${UXV_CONFIG_DIR:-$SCRIPT_DIR/../../config}"

echo '=== Build services ==='
if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  (
    cd "$CORE"
    cargo build --release -p furia-core-server -p dev-atak-server -p counter-uas-director -p sapient-simulator 2>&1 | tail -5
  )
  (
    cd "$S1"
    cargo build --release -p s1-sim-server --bins 2>&1 | tail -5
  )
  echo '  Build complete'
else
  echo '  SKIP_BUILD=1 — using existing binaries'
fi

echo '=== Start Core C-UAS services ==='
NATS_URL="$NATS_URL" "$CORE/target/release/dev-atak-server" >"$LOG_DIR/dev-atak.log" 2>&1 & ALL_PIDS+=("$!")
NATS_URL="$NATS_URL" "$CORE/target/release/furia-core-server" >"$LOG_DIR/core.log" 2>&1 & ALL_PIDS+=("$!")
NATS_URL="$NATS_URL" UXV_CONFIG_DIR="$UXV_CONFIG_DIR" RUST_LOG=debug "$CORE/target/release/counter-uas-director" >"$LOG_DIR/cuas.log" 2>&1 & ALL_PIDS+=("$!")
wait_http http://127.0.0.1:8080/health 'ATAK dev server'
wait_http http://127.0.0.1:3000/health 'Furia Core'
wait_log "$LOG_DIR/cuas.log" 'C-UAS Director started' 'C-UAS director (NATS-only)' 15

echo '=== Start S1 simulation service ==='
(
  cd "$S1"
  exec ./target/release/s1-sim-server --nats-url "$NATS_URL" --port 3227
) >"$LOG_DIR/s1.log" 2>&1 & ALL_PIDS+=("$!")
wait_http http://127.0.0.1:3227/api/v1/scenarios 'S1 Sim Server' 90

echo '=== Start C-UAS health injector ==='
"$S1/target/release/cuas-health-injector" --nats-url "$NATS_URL" >"$LOG_DIR/s1-health.log" 2>&1 & ALL_PIDS+=("$!")
sleep 2

echo '=== Start SAPIENT simulator ==='
NATS_URL="$NATS_URL" "$CORE/target/release/sapient-simulator" --target-lat=44.8283 --target-lon=-0.7156 >"$LOG_DIR/sapient.log" 2>&1 & ALL_PIDS+=("$!")

echo '=== Start Furia C2 ==='
(
  cd "$C2"
  # Dependencies already installed; skip pnpm install to avoid hanging
  NATS_URL="$NATS_URL" exec npx vite --host 127.0.0.1 --port 4180 --strictPort
) >"$LOG_DIR/c2.log" 2>&1 & ALL_PIDS+=("$!")
wait_http http://127.0.0.1:4180 'Furia C2' 90

echo '=== Start verifiers ==='
VERIFIER_PIDS=""
python3 "$SCRIPT_DIR/verify.py" >"$LOG_DIR/verify.log" 2>&1 & VERIFIER_PIDS="$VERIFIER_PIDS $!"; ALL_PIDS+=("$!")
python3 "$SCRIPT_DIR/verify_origin.py" >"$LOG_DIR/verify-origin.log" 2>&1 & VERIFIER_PIDS="$VERIFIER_PIDS $!"; ALL_PIDS+=("$!")
python3 "$SCRIPT_DIR/verify_comm_denied.py" >"$LOG_DIR/verify-comm-denied.log" 2>&1 & VERIFIER_PIDS="$VERIFIER_PIDS $!"; ALL_PIDS+=("$!")
echo '  Verifiers started'
sleep 2  # Allow subscriptions to establish before replay starts

echo '=== Start deterministic replay ==='
NATS_URL="$NATS_URL" python3 "$SCRIPT_DIR/replay.py" >"$LOG_DIR/replay.log" 2>&1 & ALL_PIDS+=("$!")

cat <<BODEOF

============================================
  FURIA BORDEAUX GOLDEN DEMO RUNNING
============================================
  NATS TCP:   127.0.0.1:4222
  NATS WS:    ws://127.0.0.1:9222
  Core:       http://127.0.0.1:3000
  C2:         http://127.0.0.1:4180
  S1:         http://127.0.0.1:3227
  Logs:       $LOG_DIR
============================================

BODEOF

# Wait for replay to finish
echo '=== Waiting for replay ==='
if [[ ${#ALL_PIDS[@]} -gt 0 ]]; then
  wait "${ALL_PIDS[@]: -1}" 2>/dev/null || true
fi
echo '  Replay done'

# Wait for verifiers to finish (they exit via --count after expected messages)
echo '=== Waiting for verifiers ==='
for pid in $VERIFIER_PIDS; do
  wait "$pid" 2>/dev/null || true
done
echo '  Verifiers done'

echo
echo '=== Verifier results ==='
PASSED=true

for vl in verify.log verify-origin.log verify-comm-denied.log; do
  log="$LOG_DIR/$vl"
  if [[ -f "$log" ]]; then
    if grep -q "PASS" "$log"; then
      echo "  ✅ $vl: PASS"
    elif grep -q "FAIL" "$log"; then
      echo "  ❌ $vl: FAIL"
      tail -3 "$log"
      PASSED=false
    else
      echo "  ⚠️  $vl: no result"
      tail -5 "$log"
      PASSED=false
    fi
  else
    echo "  ❌ $vl: not found"
    PASSED=false
  fi
done

echo
if $PASSED; then
  echo '============================================'
  echo '  ✅ BORDEAUX C-UAS GOLDEN DEMO: PASS'
  echo '============================================'
else
  echo '============================================'
  echo '  ❌ BORDEAUX C-UAS GOLDEN DEMO: FAIL'
  echo '============================================'
fi

if [[ "$AUTO_EXIT" == "1" ]]; then
  if $PASSED; then exit 0; else exit 1; fi
fi