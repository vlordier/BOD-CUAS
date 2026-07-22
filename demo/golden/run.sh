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
if [[ "${1:-}" == "--doctor" ]]; then exec bash "$SCRIPT_DIR/doctor.sh"; fi
bash "$SCRIPT_DIR/doctor.sh"
echo
echo '=== Start NATS JetStream backbone ==='
if command -v nats-server >/dev/null 2>&1; then
  nats-server -js -p 4222 >"$LOG_DIR/nats.log" 2>&1 & PIDS+=("$!")
else
  name="furia-bod-nats-$$"
  docker run --rm --name "$name" -p 4222:4222 nats:2.10-alpine -js >"$LOG_DIR/nats.log" 2>&1 &
  PIDS+=("$!"); CONTAINERS+=("$name")
fi
wait_tcp 127.0.0.1 4222 'NATS JetStream'
export NATS_URL="${NATS_URL:-nats://127.0.0.1:4222}"
export DEMO_SPEED="${DEMO_SPEED:-4.0}"

echo '=== Build Core + S1 demo services ==='
(
  cd "$CORE"
  cargo build --release -p furia-core-server -p dev-atak-server -p counter-uas-director -p sapient-simulator
)
(
  cd "$S1"
  cargo build --release -p s1-sim-server
)

echo '=== Start Core C-UAS services ==='
NATS_URL="$NATS_URL" "$CORE/target/release/dev-atak-server" >"$LOG_DIR/dev-atak.log" 2>&1 & PIDS+=("$!")
NATS_URL="$NATS_URL" "$CORE/target/release/furia-core-server" >"$LOG_DIR/core.log" 2>&1 & PIDS+=("$!")
NATS_URL="$NATS_URL" "$CORE/target/release/counter-uas-director" >"$LOG_DIR/cuas.log" 2>&1 & PIDS+=("$!")
wait_http http://127.0.0.1:8080/health 'ATAK dev server'
wait_http http://127.0.0.1:3000/health 'Furia Core'
wait_http http://127.0.0.1:3475/health 'C-UAS director'

echo '=== Start S1 simulation service on JetStream ==='
(
  cd "$S1"
  exec ./target/release/s1-sim-server --nats-url "$NATS_URL" --port 3227
) >"$LOG_DIR/s1.log" 2>&1 & PIDS+=("$!")
wait_http http://127.0.0.1:3227/api/v1/scenarios 'S1 Sim Server' 90

echo '=== Start SAPIENT simulator on JetStream ==='
NATS_URL="$NATS_URL" "$CORE/target/release/sapient-simulator" --target-lat 44.8283 --target-lon -0.7156 >"$LOG_DIR/sapient.log" 2>&1 & PIDS+=("$!")

echo '=== Start Furia C2 ==='
(
  cd "$C2"
  pnpm install --frozen-lockfile
  NATS_URL="$NATS_URL" exec pnpm dev --host 127.0.0.1
) >"$LOG_DIR/c2.log" 2>&1 & PIDS+=("$!")
wait_http http://127.0.0.1:5173 'Furia C2' 90

echo '=== Arm closed-loop acceptance monitor ==='
NATS_URL="$NATS_URL" DEMO_SPEED="$DEMO_SPEED" python3 "$SCRIPT_DIR/verify.py" >"$LOG_DIR/verify.log" 2>&1 &
VERIFY_PID=$!
PIDS+=("$VERIFY_PID")
sleep 0.5

echo '=== Start deterministic operational replay ==='
NATS_URL="$NATS_URL" DEMO_SPEED="$DEMO_SPEED" python3 "$SCRIPT_DIR/replay.py" >"$LOG_DIR/replay.log" 2>&1 &
REPLAY_PID=$!
PIDS+=("$REPLAY_PID")

# Do not declare the demo ready until the complete policy -> command -> actuator
# loop has been observed. This makes the golden path an executable acceptance test.
if ! wait "$VERIFY_PID"; then
  echo 'ERROR: Bordeaux golden demo acceptance failed.' >&2
  cat "$LOG_DIR/verify.log" >&2 || true
  exit 1
fi
printf '%-28s ✅\n' 'Closed-loop acceptance'

cat <<EOF

FURIA BORDEAUX GOLDEN DEMO READY

JetStream:  $NATS_URL
Core:       http://127.0.0.1:3000
C2:         http://127.0.0.1:5173
C-UAS:      http://127.0.0.1:3475
S1:         http://127.0.0.1:3227
SAPIENT:    publishing to JetStream stream FURIA_CUAS
Timeline:   $SCRIPT_DIR/timeline.yaml
Replay log: $LOG_DIR/replay.log
Verify log: $LOG_DIR/verify.log
Logs:       $LOG_DIR

Transport policy: NATS JetStream only. No Zenoh transport is used by the golden path.
Acceptance proved: S1 plan -> executing FSM -> Core policy abort -> S1 abort result -> Aborted/SafeHold FSM.
Press Ctrl-C to stop all demo processes.
EOF
wait
