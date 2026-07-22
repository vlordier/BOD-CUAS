#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${FURIA_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"
CORE="$ROOT/furia-core"
C2="$ROOT/furia-c2"
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
echo '=== Start NATS control/data bus ==='
if command -v nats-server >/dev/null 2>&1; then
  nats-server -p 4222 >"$LOG_DIR/nats.log" 2>&1 & PIDS+=("$!")
else
  name="furia-bod-nats-$$"
  docker run --rm --name "$name" -p 4222:4222 nats:2.10-alpine >"$LOG_DIR/nats.log" 2>&1 &
  PIDS+=("$!"); CONTAINERS+=("$name")
fi
wait_tcp 127.0.0.1 4222 'NATS'
echo '=== Bordeaux golden demo: build Core services ==='
(
  cd "$CORE"
  cargo build --release -p furia-core-server -p dev-atak-server -p counter-uas-director -p sapient-simulator
)
echo '=== Start Core C-UAS services ==='
"$CORE/target/release/dev-atak-server" >"$LOG_DIR/dev-atak.log" 2>&1 & PIDS+=("$!")
"$CORE/target/release/furia-core-server" >"$LOG_DIR/core.log" 2>&1 & PIDS+=("$!")
"$CORE/target/release/counter-uas-director" >"$LOG_DIR/cuas.log" 2>&1 & PIDS+=("$!")
wait_http http://127.0.0.1:8080/health 'ATAK dev server'
wait_http http://127.0.0.1:3000/health 'Furia Core'
wait_http http://127.0.0.1:3475/health 'C-UAS director'
if [[ -n "${ZENOH_CONNECT:-}" ]]; then
  echo "=== Start SAPIENT simulator via Zenoh ($ZENOH_CONNECT) ==="
  ZENOH_CONNECT="$ZENOH_CONNECT" "$CORE/target/release/sapient-simulator" >"$LOG_DIR/sapient.log" 2>&1 & PIDS+=("$!")
else
  echo 'SAPIENT simulator not started: set ZENOH_CONNECT to an available Zenoh router.'
  echo 'This avoids falsely presenting its dry-run mode as connected to the NATS-only C-UAS director.'
fi
echo '=== Start Furia C2 ==='
(
  cd "$C2"
  pnpm install --frozen-lockfile
  exec pnpm dev --host 127.0.0.1
) >"$LOG_DIR/c2.log" 2>&1 & PIDS+=("$!")
wait_http http://127.0.0.1:5173 'Furia C2' 90
cat <<EOF

FURIA BORDEAUX GOLDEN DEMO READY

NATS:       nats://127.0.0.1:4222
Core:       http://127.0.0.1:3000
C2:         http://127.0.0.1:5173
C-UAS:      http://127.0.0.1:3475
SAPIENT:    ${ZENOH_CONNECT:+connected via $ZENOH_CONNECT}${ZENOH_CONNECT:-not started (set ZENOH_CONNECT)}
Timeline:   $SCRIPT_DIR/timeline.yaml
Logs:       $LOG_DIR

Next vertical-slice target: drive timeline.yaml through normalized surveillance events,
operator authorization, S1 plan/execution, and airport safety abort.
Press Ctrl-C to stop all demo processes.
EOF
wait
