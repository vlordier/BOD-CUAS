#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/nats-runtime.sh"
NATS_TCP_PORT="${DEMO_NATS_TCP_PORT:-4222}"
NATS_WS_PORT="${DEMO_NATS_WS_PORT:-9222}"

scratch="$(mktemp -d "${TMPDIR:-/tmp}/bod-cuas-nats-test.XXXXXXXX")"
trap 'rm -rf -- "$scratch"' EXIT
TMPDIR="$scratch"
export TMPDIR

first="$(create_demo_nats_state_dir)"
second="$(create_demo_nats_state_dir)"
[[ "$first" != "$second" ]]
[[ "$first" != "/tmp/furia-bod-nats-js" ]]

render_demo_nats_config "$SCRIPT_DIR/nats.conf" "$first/nats.conf" "$first" "$NATS_TCP_PORT" "$NATS_WS_PORT"
render_demo_nats_config "$SCRIPT_DIR/nats.conf" "$second/nats.conf" "$second" "$NATS_TCP_PORT" "$NATS_WS_PORT"

grep -Fqx "port: $NATS_TCP_PORT" "$first/nats.conf"
grep -Fqx "  port: $NATS_WS_PORT" "$first/nats.conf"
grep -Fqx "  store_dir: \"$first/jetstream\"" "$first/nats.conf"
grep -Fqx "  store_dir: \"$second/jetstream\"" "$second/nats.conf"
[[ -d "$first/jetstream" && -d "$second/jetstream" ]]

# The repository clean target must never kill processes or clear shared state.
clean_recipe="$(sed -n '/^clean:/,$p' "$SCRIPT_DIR/../../Makefile")"
if printf '%s\n' "$clean_recipe" | grep -En 'pkill|/tmp/furia-bod-nats-js|rm -rf'; then
  echo 'Makefile clean must not use global process or shared-state cleanup' >&2
  exit 1
fi

echo 'NATS state isolation tests: passed'
