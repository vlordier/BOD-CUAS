#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${FURIA_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"
CORE="$ROOT/furia-core"
C2="$ROOT/furia-c2"
S1="$ROOT/S1"
LOG_DIR="${TMPDIR:-/tmp}/furia-bod-golden"
mkdir -p "$LOG_DIR"
PIDS=()
CONTAINERS=()
cleanup() {
  local rc=$?
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  for container in "${CONTAINERS[@]:-}"; do docker rm -f "$container" >/dev/null 2>&1 || true; done
  wait 2>/dev/null || true
  exit "$rc"
}
trap cleanup EXIT INT TERM
wait_http() {
  local url="$1" label="$2" max="${3:-60}" i=0
  until curl -sf "$url" >/dev/null 2>&1; do
    (( i++ >= max )) && { echo "ERROR: $label not healthy: $url"; return 1; }
    sleep 1
  done
  printf '%-28s ✅\n' "$label"
}
wait_tcp() {
  local host="$1" port="$2" label="$3" max="${4:-30}" i=0
  until (echo >/dev/tcp/"$host"/"$port") >/dev/null 2>&1; do
    (( i++ >= max )) && { echo "ERROR: $label not ready on $host:$port"; return 1; }
    sleep 1
  done
  printf '%-28s ✅\n' "$label"
}
wait_process() {
  local pid="$1" label="$2" seconds="${3:-2}"
  sleep "$seconds"
  if kill -0 "$pid" 2>/dev/null; then printf '%-28s ✅\n' "$label"; else echo "ERROR: $label exited during startup" >&2; return 1; fi
}
assert_alive() {
  local pid="$1" label="$2" log="$3"
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "ERROR: $label exited unexpectedly" >&2
    tail -200 "$log" >&2 2>/dev/null || true
    return 1
  fi
}
if [[ "${1:-}" == "--doctor" ]]; then exec bash "$SCRIPT_DIR/doctor.sh"; fi
bash "$SCRIPT_DIR/doctor.sh"
echo
echo '=== Start NATS JetStream backbone ==='
if command -v nats-server >/dev/null 2>&1; then
  nats-server -c "$SCRIPT_DIR/nats.conf" >"$LOG_DIR/nats.log" 2>&1 & PIDS+=("$!")
else
  name="furia-bod-nats-$$"
  docker run --rm --name "$name" -p 4222:4222 -p 9222:9222 -v "$SCRIPT_DIR/nats.conf:/etc/nats/nats.conf:ro" nats:2.10-alpine -c /etc/nats/nats.conf >"$LOG_DIR/nats.log" 2>&1 &
  PIDS+=("$!"); CONTAINERS+=("$name")
fi
wait_tcp 127.0.0.1 4222 'NATS JetStream TCP'
wait_tcp 127.0.0.1 9222 'NATS WebSocket'
export NATS_URL="${NATS_URL:-nats://127.0.0.1:4222}"
export FURIA_NATS_URL="${FURIA_NATS_URL:-$NATS_URL}"
export VITE_NATS_WS_URL="${VITE_NATS_WS_URL:-ws://127.0.0.1:9222}"
export UXV_CONFIG_DIR="${UXV_CONFIG_DIR:-$SCRIPT_DIR/../../config}"
export DEMO_SPEED="${DEMO_SPEED:-4.0}"

echo '=== Build Core + S1 demo services ==='
(cd "$CORE" && cargo build --release -p furia-core-server -p dev-atak-server -p counter-uas-director -p sapient-simulator)
(cd "$S1" && cargo build --release -p s1-sim-server --bins)

echo '=== Start Core airport-safety services ==='
NATS_URL="$NATS_URL" "$CORE/target/release/dev-atak-server" >"$LOG_DIR/dev-atak.log" 2>&1 & ATAK_PID=$!; PIDS+=("$ATAK_PID")
NATS_URL="$NATS_URL" FURIA_NATS_URL="$FURIA_NATS_URL" "$CORE/target/release/furia-core-server" >"$LOG_DIR/core.log" 2>&1 & CORE_PID=$!; PIDS+=("$CORE_PID")
NATS_URL="$NATS_URL" UXV_CONFIG_DIR="$UXV_CONFIG_DIR" "$CORE/target/release/counter-uas-director" >"$LOG_DIR/cuas.log" 2>&1 & CUAS_PID=$!; PIDS+=("$CUAS_PID")
wait_http http://127.0.0.1:8080/health 'ATAK dev server'
wait_http http://127.0.0.1:3000/health 'Furia Core'
wait_process "$CUAS_PID" 'C-UAS director (NATS-only)' 2

echo '=== Start S1 simulation services on JetStream ==='
(cd "$S1" && exec ./target/release/s1-sim-server --nats-url "$NATS_URL" --port 3227) >"$LOG_DIR/s1.log" 2>&1 & S1_PID=$!; PIDS+=("$S1_PID")
wait_http http://127.0.0.1:3227/api/v1/scenarios 'S1 Sim Server' 90
(cd "$S1" && exec ./target/release/cuas-health-injector --nats-url "$NATS_URL") >"$LOG_DIR/s1-health.log" 2>&1 & S1_HEALTH_PID=$!; PIDS+=("$S1_HEALTH_PID")
wait_process "$S1_HEALTH_PID" 'S1 bounded health injector' 2

echo '=== Start SAPIENT simulator on JetStream ==='
NATS_URL="$NATS_URL" "$CORE/target/release/sapient-simulator" --target-lat 44.8283 --target-lon -0.7156 >"$LOG_DIR/sapient.log" 2>&1 & SAPIENT_PID=$!; PIDS+=("$SAPIENT_PID")

echo '=== Start Furia C2 on fixed port 5173 ==='
(cd "$C2" && pnpm install --frozen-lockfile && VITE_NATS_WS_URL="$VITE_NATS_WS_URL" NATS_URL="$NATS_URL" exec pnpm dev --host 127.0.0.1 --port 5173 --strictPort) >"$LOG_DIR/c2.log" 2>&1 & C2_PID=$!; PIDS+=("$C2_PID")
wait_http http://127.0.0.1:5173 'Furia C2' 90

echo '=== Arm closed-loop + threat-origin acceptance monitors ==='
NATS_URL="$NATS_URL" DEMO_SPEED="$DEMO_SPEED" python3 "$SCRIPT_DIR/verify.py" >"$LOG_DIR/verify.log" 2>&1 & VERIFY_PID=$!; PIDS+=("$VERIFY_PID")
NATS_URL="$NATS_URL" DEMO_SPEED="$DEMO_SPEED" python3 "$SCRIPT_DIR/verify_origin.py" >"$LOG_DIR/verify-origin.log" 2>&1 & ORIGIN_VERIFY_PID=$!; PIDS+=("$ORIGIN_VERIFY_PID")
sleep 0.5

echo '=== Start deterministic operational + ASTERIX/RF/acoustic replay ==='
NATS_URL="$NATS_URL" DEMO_SPEED="$DEMO_SPEED" python3 "$SCRIPT_DIR/replay.py" >"$LOG_DIR/replay.log" 2>&1 & REPLAY_PID=$!; PIDS+=("$REPLAY_PID")

if ! wait "$VERIFY_PID"; then
  echo 'ERROR: Bordeaux golden demo acceptance failed.' >&2
  cat "$LOG_DIR/verify.log" >&2 || true
  tail -200 "$LOG_DIR/cuas.log" >&2 || true
  tail -200 "$LOG_DIR/s1.log" >&2 || true
  tail -200 "$LOG_DIR/s1-health.log" >&2 || true
  tail -200 "$LOG_DIR/c2.log" >&2 || true
  exit 1
fi
printf '%-28s ✅\n' 'Closed-loop acceptance'
if ! wait "$ORIGIN_VERIFY_PID"; then
  echo 'ERROR: Bordeaux threat-origin acceptance failed.' >&2
  cat "$LOG_DIR/verify-origin.log" >&2 || true
  tail -200 "$LOG_DIR/cuas.log" >&2 || true
  exit 1
fi
printf '%-28s ✅\n' 'Threat-origin acceptance'

if ! wait "$REPLAY_PID"; then
  echo 'ERROR: Bordeaux deterministic replay failed.' >&2
  cat "$LOG_DIR/replay.log" >&2 || true
  exit 1
fi
printf '%-28s ✅\n' 'Deterministic replay'

assert_alive "$ATAK_PID" 'ATAK dev server' "$LOG_DIR/dev-atak.log"
assert_alive "$CORE_PID" 'Furia Core' "$LOG_DIR/core.log"
assert_alive "$CUAS_PID" 'C-UAS director' "$LOG_DIR/cuas.log"
assert_alive "$S1_PID" 'S1 Sim Server' "$LOG_DIR/s1.log"
assert_alive "$S1_HEALTH_PID" 'S1 health injector' "$LOG_DIR/s1-health.log"
assert_alive "$SAPIENT_PID" 'SAPIENT simulator' "$LOG_DIR/sapient.log"
assert_alive "$C2_PID" 'Furia C2' "$LOG_DIR/c2.log"
printf '%-28s ✅\n' 'Post-scenario liveness'

cat <<EOF

FURIA BORDEAUX GOLDEN DEMO READY

JetStream TCP:  $NATS_URL
NATS WebSocket: $VITE_NATS_WS_URL
Core:           http://127.0.0.1:3000
C2:             http://127.0.0.1:5173
S1:             http://127.0.0.1:3227
C-UAS director: NATS-only process (log: $LOG_DIR/cuas.log)
S1 health:      bounded guard injector (log: $LOG_DIR/s1-health.log)
SAPIENT:        publishing to JetStream
ASTERIX:        CAT015/016 + CAT021 + CAT048(optional) + CAT062/063 + CAT129
Origin sensing: synthetic RF AoA/TDOA + acoustic corroboration, uncertainty preserved
Auth config:    $UXV_CONFIG_DIR/cuas-authorizations.yaml
Timeline:       $SCRIPT_DIR/timeline.yaml
Replay log:     $LOG_DIR/replay.log
Verify log:     $LOG_DIR/verify.log
Origin verify:  $LOG_DIR/verify-origin.log
Logs:           $LOG_DIR

Acceptance proved: surveillance -> Core-owned threat-origin/emitter inference -> protected-volume risk/incident -> sensor degradation -> named bounded delegation -> S1 execution evidence -> bounded comm-denied continuation -> recovery -> civilian-safety abort -> final correlated Aborted/SafeHold evidence.
EOF

if [[ "${GOLDEN_EXIT_AFTER_ACCEPTANCE:-0}" == "1" ]]; then
  echo 'SMOKE RESULT: PASS'
  exit 0
fi

echo 'Press Ctrl-C to stop all demo processes.'
wait
