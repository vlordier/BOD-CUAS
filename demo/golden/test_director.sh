#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${TMPDIR:-/tmp}/furia-bod-golden"
mkdir -p "$LOG_DIR"

pkill -f "nats-server" 2>/dev/null || true
pkill -f "counter-uas-director" 2>/dev/null || true
pkill -f "replay.py" 2>/dev/null || true
sleep 2

nats-server -c "$SCRIPT_DIR/nats.conf" >"$LOG_DIR/nats.log" 2>&1 &
NATS_PID=$!
sleep 2

if ! kill -0 $NATS_PID 2>/dev/null; then
    echo "NATS failed"
    cat "$LOG_DIR/nats.log"
    exit 1
fi
echo "NATS started (PID: $NATS_PID)"

RUST_LOG=debug /Users/vincent/Work/furia-core/target/release/counter-uas-director >"$LOG_DIR/cuas.log" 2>&1 &
DIRECTOR_PID=$!
sleep 2

if ! kill -0 $DIRECTOR_PID 2>/dev/null; then
    echo "Director failed"
    cat "$LOG_DIR/cuas.log"
    exit 1
fi
echo "Director started (PID: $DIRECTOR_PID)"

cd "$SCRIPT_DIR" && NATS_URL=nats://127.0.0.1:4222 python3 replay.py >"$LOG_DIR/replay.log" 2>&1 &
REPLAY_PID=$!

wait $REPLAY_PID 2>/dev/null || true
echo "Replay done"

sleep 2

kill $DIRECTOR_PID 2>/dev/null || true
wait $DIRECTOR_PID 2>/dev/null || true

echo ""
echo "=== Director log ==="
cat "$LOG_DIR/cuas.log"

echo ""
echo "=== Replay log ==="
cat "$LOG_DIR/replay.log"

kill $NATS_PID 2>/dev/null || true
wait $NATS_PID 2>/dev/null || true

echo ""
echo "Done"