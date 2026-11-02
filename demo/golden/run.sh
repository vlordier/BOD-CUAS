#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${FURIA_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"
CORE="$ROOT/furia-core"
C2="$ROOT/furia-c2"
S1="$ROOT/S1"
# Keep logs reproducible in CI or a shared rehearsal host without requiring
# edits to the runner. The default remains an isolated temporary directory.
LOG_DIR="${DEMO_LOG_DIR:-${TMPDIR:-/tmp}/furia-bod-golden}"
mkdir -p "$LOG_DIR"
source "$SCRIPT_DIR/runtime-config.sh"
load_demo_runtime_config
validate_demo_runtime_config

NATS_MODE="${DEMO_NATS_MODE:-auto}"
if [[ "$NATS_MODE" == "external" || "$NATS_MODE" == "headless" ]]; then
  echo "ERROR: run.sh owns a local NATS broker and requires DEMO_NATS_MODE=local (or auto)." >&2
  echo "       Use doctor.sh for external/headless diagnostics, or provide a local broker for the full UI run." >&2
  exit 2
fi

ALL_PIDS=()
ALL_CONTAINERS=()
source "$SCRIPT_DIR/nats-runtime.sh"
NATS_STATE_DIR=""

cleanup() {
  local rc=$?
  echo "=== Cleaning up ==="
  for pid in "${ALL_PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  for c in "${ALL_CONTAINERS[@]:-}"; do docker rm -f "$c" >/dev/null 2>&1 || true; done
  wait 2>/dev/null || true
  # Only remove the state directory allocated by this runner instance.
  if [[ -n "$NATS_STATE_DIR" && -f "$NATS_STATE_DIR/.furia-owned" ]]; then
    rm -rf -- "$NATS_STATE_DIR"
  fi
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

if [[ "${1:-}" == "--doctor" ]]; then exec bash "$SCRIPT_DIR/doctor.sh"; fi
DEMO_NATS_TCP_PORT="$NATS_TCP_PORT" DEMO_NATS_WS_PORT="$NATS_WS_PORT" \
  DEMO_SAPIENT_ADAPTER_PORT="$SAPIENT_ADAPTER_PORT" \
  DEMO_CORE_PORT="$CORE_PORT" DEMO_S1_PORT="$S1_PORT" DEMO_C2_PORT="$C2_PORT" DEMO_ATAK_PORT="$ATAK_PORT" \
  DEMO_SAPIENT_PATH="$SAPIENT_PATH" DEMO_CUAS_PROJECTION_MODE="$CUAS_PROJECTION_MODE" \
  NATS_URL="$NATS_URL" VITE_NATS_WS_URL="$VITE_NATS_WS_URL" \
  bash "$SCRIPT_DIR/doctor.sh"
echo

echo '=== Start NATS JetStream (TCP + WebSocket) ==='
if command -v nats-server >/dev/null 2>&1; then
  NATS_STATE_DIR="$(create_demo_nats_state_dir)"
  touch "$NATS_STATE_DIR/.furia-owned"
  render_demo_nats_config "$SCRIPT_DIR/nats.conf" "$NATS_STATE_DIR/nats.conf" "$NATS_STATE_DIR" 4222 9222
  nats-server -c "$NATS_STATE_DIR/nats.conf" >"$LOG_DIR/nats.log" 2>&1 & ALL_PIDS+=("$!")
else
  name="furia-bod-nats-$$"
  docker run --rm --name "$name" -p "$NATS_TCP_PORT:4222" -p "$NATS_WS_PORT:9222" \
    nats:2.10-alpine -js --websocket_port 9222 \
    >"$LOG_DIR/nats.log" 2>&1 &
  ALL_PIDS+=("$!"); ALL_CONTAINERS+=("$name")
fi
wait_tcp "$NATS_TCP_PORT" 'NATS TCP'
wait_tcp "$NATS_WS_PORT" 'NATS WebSocket'
export NATS_URL="${NATS_URL:-nats://127.0.0.1:$NATS_TCP_PORT}"
export FURIA_NATS_URL="$NATS_URL"
# The browser adapter uses an explicit WebSocket endpoint. Keep it
# configurable for remote/rehearsal deployments while preserving the local
# default used by the deterministic demo.
export VITE_NATS_WS_URL="${VITE_NATS_WS_URL:-ws://127.0.0.1:$NATS_WS_PORT}"
export UXV_CONFIG_DIR="${UXV_CONFIG_DIR:-$SCRIPT_DIR/../../config}"

# Projection ownership is explicit. The external mode is the canonical
# synthetic demo path; compatibility remains available for migration tests.
echo "  Canonical operational projection owner: $CUAS_PROJECTION_MODE"

echo "  SAPIENT path: $SAPIENT_PATH"

ATAK_MODE="${DEMO_ATAK_MODE:-auto}"
if [[ "${DEMO_SKIP_ATAK:-0}" == "1" ]]; then ATAK_MODE="skip"; fi
if [[ "$ATAK_MODE" == "auto" ]] && command -v lsof >/dev/null 2>&1 && lsof -i :"$ATAK_PORT" 2>/dev/null | grep -q LISTEN; then
  echo '  ATAK development server auto-disabled because :8080 is occupied'
  ATAK_MODE="skip"
fi
if [[ "$ATAK_MODE" != "auto" && "$ATAK_MODE" != "required" && "$ATAK_MODE" != "skip" ]]; then
  echo "ERROR: DEMO_ATAK_MODE must be auto, required, or skip (got $ATAK_MODE)"
  exit 1
fi

echo '=== Build services ==='
if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  if [[ "$SAPIENT_PATH" == "protobuf-adapter" ]]; then
    (
      cd "$CORE"
      cargo build --release -p furia-core-server -p dev-atak-server -p sapient-simulator -p sapient-adapter 2>&1 | tail -5
    )
  else
    (
      cd "$CORE"
      cargo build --release -p furia-core-server -p dev-atak-server -p sapient-simulator 2>&1 | tail -5
    )
  fi
  if [[ "$CUAS_PROJECTION_MODE" == "furia-cuas" ]]; then
    (
      cd "$ROOT/furia-cuas"
      cargo build --release -p furia-cuas-simulator --bin furia-cuas-publisher 2>&1 | tail -5
    )
  fi
  (
    cd "$S1"
    cargo build --release -p s1-sim-server --bins 2>&1 | tail -5
  )
  echo '  Build complete'
else
  echo '  SKIP_BUILD=1 — using existing binaries'
fi

if [[ "$CUAS_PROJECTION_MODE" == "furia-cuas" ]]; then
  PUBLISHER_BIN="${FURIA_CUAS_PUBLISHER_BIN:-$ROOT/furia-cuas/target/release/furia-cuas-publisher}"
  [[ -x "$PUBLISHER_BIN" ]] || { echo "ERROR: canonical publisher missing: $PUBLISHER_BIN" >&2; exit 1; }
  echo '=== Start canonical furia-cuas projection publisher ==='
  nats --server "$NATS_URL" sub furia.cuas.operational-projection --count=1 --timeout=15s >"$LOG_DIR/canonical-projection.jsonl" 2>&1 & ALL_PIDS+=("$!")
  if [[ "$SAPIENT_PATH" == "protobuf-adapter" ]]; then
    NATS_URL="$NATS_URL" "$PUBLISHER_BIN" --nats-url "$NATS_URL" --from-sapient \
      >"$LOG_DIR/furia-cuas-publisher.log" 2>&1 & ALL_PIDS+=("$!")
    echo '  Projection source: normalized SAPIENT adapter handoff'
  else
    NATS_URL="$NATS_URL" "$PUBLISHER_BIN" --nats-url "$NATS_URL" --simulate \
      --ticks "${DEMO_CUAS_PUBLISHER_TICKS:-3600}" \
      --interval-ms "${DEMO_CUAS_PUBLISHER_INTERVAL_MS:-1000}" \
      >"$LOG_DIR/furia-cuas-publisher.log" 2>&1 & ALL_PIDS+=("$!")
    wait_log "$LOG_DIR/canonical-projection.jsonl" 'furia.cuas.operational-projection' 'canonical furia-cuas projection' 15
    echo '  Projection provenance: furia-cuas-publisher synthetic replay'
  fi
fi

echo '=== Start Core services ==='
if [[ "$ATAK_MODE" != "skip" ]]; then
  NATS_URL="$NATS_URL" ATAK_PORT="$ATAK_PORT" "$CORE/target/release/dev-atak-server" >"$LOG_DIR/dev-atak.log" 2>&1 & ALL_PIDS+=("$!")
else
  echo '  ATAK development server skipped (C2 replay does not require it)'
fi
NATS_URL="$NATS_URL" FURIA_PORT="$CORE_PORT" "$CORE/target/release/furia-core-server" >"$LOG_DIR/core.log" 2>&1 & ALL_PIDS+=("$!")
if [[ "$ATAK_MODE" != "skip" ]]; then wait_http "http://127.0.0.1:$ATAK_PORT/health" 'ATAK dev server'; fi
wait_http "http://127.0.0.1:$CORE_PORT/health" 'Furia Core'

if [[ "$SAPIENT_PATH" == "protobuf-adapter" ]]; then
  echo '=== Start real SAPIENT Protobuf adapter ==='
  NATS_URL="$NATS_URL" SAPIENT_ADAPTER_PORT="$SAPIENT_ADAPTER_PORT" "$CORE/target/release/sapient-adapter" >"$LOG_DIR/sapient-adapter.log" 2>&1 & ALL_PIDS+=("$!")
  wait_http "http://127.0.0.1:$SAPIENT_ADAPTER_PORT/health" 'SAPIENT Protobuf adapter'
fi

echo '=== Start S1 simulation service ==='
(
  cd "$S1"
  exec ./target/release/s1-sim-server --nats-url "$NATS_URL" --port "$S1_PORT"
) >"$LOG_DIR/s1.log" 2>&1 & ALL_PIDS+=("$!")
wait_http "http://127.0.0.1:$S1_PORT/api/v1/scenarios" 'S1 Sim Server' 90

echo '=== Start C-UAS health injector ==='
"$S1/target/release/cuas-health-injector" --nats-url "$NATS_URL" >"$LOG_DIR/s1-health.log" 2>&1 & ALL_PIDS+=("$!")
wait_log "$LOG_DIR/s1-health.log" 'cuas-health-injector: subscribed to' 'C-UAS health injector' 15
wait_log "$LOG_DIR/s1-health.log" 'subscribed to swarm.command.abort' 'C-UAS abort evidence bridge' 15

echo '=== Start SAPIENT simulator ==='
if [[ "$SAPIENT_PATH" == "protobuf-adapter" ]]; then
  NATS_URL="$NATS_URL" "$CORE/target/release/sapient-simulator" \
    --adapter-url "http://127.0.0.1:$SAPIENT_ADAPTER_PORT" --target-lat=44.8283 --target-lon=-0.7156 \
    >"$LOG_DIR/sapient.log" 2>&1 & ALL_PIDS+=("$!")
  wait_log "$LOG_DIR/canonical-projection.jsonl" 'furia.cuas.operational-projection' 'SAPIENT → furia-cuas canonical projection' 20
else
  NATS_URL="$NATS_URL" "$CORE/target/release/sapient-simulator" --target-lat=44.8283 --target-lon=-0.7156 >"$LOG_DIR/sapient.log" 2>&1 & ALL_PIDS+=("$!")
fi

echo '=== Start Furia C2 ==='
(
  cd "$C2"
  # Dependencies already installed; skip pnpm install to avoid hanging
  NATS_URL="$NATS_URL" VITE_NATS_WS_URL="$VITE_NATS_WS_URL" exec npx vite --host 127.0.0.1 --port "$C2_PORT" --strictPort
) >"$LOG_DIR/c2.log" 2>&1 & ALL_PIDS+=("$!")
wait_http "http://127.0.0.1:$C2_PORT" 'Furia C2' 90

if [[ "${DEMO_CONTEXT_SIMULATORS:-1}" == "1" ]]; then
  echo '=== Start labelled 3D visual-world descriptor ==='
  python3 "$ROOT/BOD-CUAS/demo/live-context/visual_world_simulator.py" --nats-url "$NATS_URL" >"$LOG_DIR/visual-world.log" 2>&1 & ALL_PIDS+=("$!")
  echo '=== Start labelled EO/IR metadata simulator ==='
  python3 "$ROOT/BOD-CUAS/demo/live-context/eo_ir_simulator.py" --nats-url "$NATS_URL" >"$LOG_DIR/eo-ir.log" 2>&1 & ALL_PIDS+=("$!")
fi

echo '=== Start verifiers ==='
VERIFIER_PIDS=""
python3 "$SCRIPT_DIR/verify.py" >"$LOG_DIR/verify.log" 2>&1 & VERIFIER_PIDS="$VERIFIER_PIDS $!"; ALL_PIDS+=("$!")
python3 "$SCRIPT_DIR/verify_origin.py" >"$LOG_DIR/verify-origin.log" 2>&1 & VERIFIER_PIDS="$VERIFIER_PIDS $!"; ALL_PIDS+=("$!")
python3 "$SCRIPT_DIR/verify_comm_denied.py" >"$LOG_DIR/verify-comm-denied.log" 2>&1 & VERIFIER_PIDS="$VERIFIER_PIDS $!"; ALL_PIDS+=("$!")
echo '  Verifiers started'
sleep 2  # Allow subscriptions to establish before replay starts

echo '=== Start deterministic replay ==='
# CI/capture preserves a deterministic fallback. For a real operator-led
# presentation use DEMO_AUTORIZE_FALLBACK=0 and authorize in the visible C2.
DEMO_SPEED="${DEMO_SPEED:-1}" DEMO_AUTORIZE_FALLBACK="${DEMO_AUTORIZE_FALLBACK:-1}" NATS_URL="$NATS_URL" python3 "$SCRIPT_DIR/replay.py" >"$LOG_DIR/replay.log" 2>&1 & ALL_PIDS+=("$!")

cat <<BODEOF

============================================
  FURIA BORDEAUX GOLDEN DEMO RUNNING
============================================
  NATS TCP:   $NATS_URL
  NATS WS:    $VITE_NATS_WS_URL
  SAPIENT adapter: 127.0.0.1:$SAPIENT_ADAPTER_PORT
  Core:       http://127.0.0.1:$CORE_PORT
  C2:         http://127.0.0.1:$C2_PORT
  S1:         http://127.0.0.1:$S1_PORT
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

# A golden-demo invocation is an acceptance command, not an interactive
# dashboard.  Its shell status must always represent the verifier outcome.
if $PASSED; then exit 0; else exit 1; fi
