#!/usr/bin/env bash
set -euo pipefail
ROOT="${FURIA_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
fail=0
check_dir() {
  local name="$1" path="$2"
  if [[ -d "$path" ]]; then printf '%-24s ✅ %s\n' "$name" "$path"; else printf '%-24s ❌ %s\n' "$name" "$path"; fail=1; fi
}
check_cmd() {
  local name="$1" cmd="$2"
  if command -v "$cmd" >/dev/null 2>&1; then printf '%-24s ✅ %s\n' "$name" "$cmd"; else printf '%-24s ❌ %s\n' "$name" "$cmd"; fail=1; fi
}
printf 'Furia Bordeaux golden demo doctor\n\n'

# The golden runner historically assumed that it owns a local NATS instance
# and its browser WebSocket port.  The current synthetic stack can instead
# consume an externally managed NATS, or run headless with TCP only.  Make the
# diagnostic mode explicit so an unavailable local port is not reported as a
# failure for those deployments.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/runtime-config.sh"
load_demo_runtime_config
validate_demo_runtime_config || exit $?
NATS_MODE="${DEMO_NATS_MODE:-auto}"
if [[ "${CUAS_EXTERNAL_NATS:-0}" == "1" || "${DEMO_EXTERNAL_NATS:-0}" == "1" ]]; then
  NATS_MODE="external"
elif [[ "${DEMO_HEADLESS:-0}" == "1" || "${DEMO_NO_UI:-0}" == "1" ]]; then
  NATS_MODE="headless"
elif [[ "$NATS_MODE" == "auto" ]]; then
  NATS_MODE="local"
fi
if [[ "$NATS_MODE" != "local" && "$NATS_MODE" != "external" && "$NATS_MODE" != "headless" ]]; then
  printf 'NATS mode must be local, external, headless, or auto (got %s)\n' "$NATS_MODE"
  exit 1
fi
NATS_WS_URL="$VITE_NATS_WS_URL"
printf '%-24s %s\n' 'NATS mode' "$NATS_MODE"
printf '%-24s %s\n' 'NATS TCP endpoint' "$NATS_URL"
if [[ "$NATS_MODE" != "headless" ]]; then
  printf '%-24s %s\n' 'NATS WebSocket endpoint' "$NATS_WS_URL"
fi

check_url() {
  local name="$1" value="$2"
  if [[ "$value" =~ ^(nats|tls|ws|wss)://[^[:space:]]+$ ]]; then
    printf '%-24s ✅ %s\n' "$name" "$value"
  else
    printf '%-24s ❌ invalid URL: %s\n' "$name" "$value"
    fail=1
  fi
}

check_nats_endpoint() {
  local name="$1" value="$2"
  if ! command -v nats >/dev/null 2>&1; then
    printf '%-24s ⚠️  nats CLI unavailable; endpoint syntax only\n' "$name"
    return 0
  fi
  if timeout 8 nats rtt -s "$value" >/dev/null 2>&1; then
    printf '%-24s ✅ reachable\n' "$name"
  else
    printf '%-24s ❌ unreachable\n' "$name"
    fail=1
  fi
}

check_url 'NATS TCP URL' "$NATS_URL"
if [[ "$NATS_MODE" != "headless" ]]; then check_url 'NATS WebSocket URL' "$NATS_WS_URL"; fi

ATAK_MODE="${DEMO_ATAK_MODE:-auto}"
if [[ "${DEMO_SKIP_ATAK:-0}" == "1" ]]; then ATAK_MODE="skip"; fi
if [[ "$ATAK_MODE" != "auto" && "$ATAK_MODE" != "required" && "$ATAK_MODE" != "skip" ]]; then
  printf 'ATAK mode must be auto, required, or skip (got %s)\n' "$ATAK_MODE"
  exit 1
fi
check_dir 'BOD-CUAS' "$ROOT/BOD-CUAS"
check_dir 'furia-core' "$ROOT/furia-core"
check_dir 'furia-ui' "$ROOT/furia-ui"
check_dir 'furia-c2' "$ROOT/furia-c2"
check_dir 'S1' "$ROOT/S1"
check_cmd 'cargo' cargo
check_cmd 'nats' nats
check_cmd 'timeout' timeout
check_cmd 'node' node
check_cmd 'pnpm' pnpm
check_cmd 'python3' python3
if [[ "$NATS_MODE" == "external" ]]; then
  check_nats_endpoint 'External NATS'
else
  check_cmd 'nats-server' nats-server
  if command -v docker >/dev/null 2>&1; then printf '%-24s ✅ docker\n' 'container runtime'; elif command -v nats-server >/dev/null 2>&1; then printf '%-24s ✅ nats-server\n' 'NATS runtime'; else printf '%-24s ❌ docker or nats-server\n' 'NATS runtime'; fail=1; fi
fi

if python3 "$SCRIPT_DIR/replay.py" --validate-profile >/dev/null 2>&1; then
  printf '%-24s ✅ selected replay profile\n' 'Replay profile'
else
  printf '%-24s ❌ selected replay profile\n' 'Replay profile'
  fail=1
fi

# Port availability
check_port() {
  local port="$1" name="$2"
  if command -v lsof >/dev/null 2>&1; then
    if lsof -i :"$port" 2>/dev/null | grep -q LISTEN; then
      printf '%-24s ❌ %s (in use)\n' "$name" ":$port"
      fail=1
    else
      printf '%-24s ✅ %s\n' "$name" ":$port"
    fi
  elif command -v ss >/dev/null 2>&1; then
    if ss -tlnp "sport = :$port" 2>/dev/null | grep -q LISTEN; then
      printf '%-24s ❌ %s (in use)\n' "$name" ":$port"
      fail=1
    else
      printf '%-24s ✅ %s\n' "$name" ":$port"
    fi
  else
    printf '%-24s ⚠️  %s (cannot check — install lsof or ss)\n' "$name" ":$port"
  fi
}
printf '\n'
if [[ "$NATS_MODE" == "local" ]]; then
  check_port "$NATS_TCP_PORT" 'NATS TCP'
  check_port "$NATS_WS_PORT" 'NATS WebSocket'
elif [[ "$NATS_MODE" == "headless" ]]; then
  check_port "$NATS_TCP_PORT" 'NATS TCP'
  printf '%-24s ⏭️  headless mode (not required)\n' 'NATS WebSocket'
else
  printf '%-24s ⏭️  externally managed\n' 'NATS local ports'
fi
if [[ "$ATAK_MODE" == "required" ]]; then
  check_port "$ATAK_PORT" 'ATAK dev server'
elif [[ "$ATAK_MODE" == "auto" ]]; then
  if command -v lsof >/dev/null 2>&1 && lsof -i :"$ATAK_PORT" 2>/dev/null | grep -q LISTEN; then
    printf '%-28s ⚠️  occupied / auto-disabled\n' "ATAK dev server :$ATAK_PORT"
  else
    printf '%-28s ✅ :%s (auto)\n' 'ATAK dev server' "$ATAK_PORT"
  fi
else
  printf '%-28s ⏭️  explicitly skipped\n' 'ATAK dev server'
fi
check_port "$CORE_PORT" 'Furia Core'
check_port "$S1_PORT" 'S1 sim server'
check_port "$C2_PORT" 'Furia C2'

if [[ "${SKIP_BUILD:-0}" == "1" ]]; then
  printf '\nSKIP_BUILD binary prerequisites\n'
  check_file() {
    local name="$1" path="$2"
    if [[ -x "$path" ]]; then printf '%-24s ✅ %s\n' "$name" "$path"; else printf '%-24s ❌ %s\n' "$name" "$path"; fail=1; fi
  }
  check_file 'dev-atak-server' "$ROOT/furia-core/target/release/dev-atak-server"
  check_file 'furia-core-server' "$ROOT/furia-core/target/release/furia-core-server"
  check_file 'sapient-simulator' "$ROOT/furia-core/target/release/sapient-simulator"
  if [[ "${DEMO_SAPIENT_PATH:-direct}" == "protobuf-adapter" ]]; then
    check_file 'sapient-adapter' "$ROOT/furia-core/target/release/sapient-adapter"
    check_port "${DEMO_SAPIENT_ADAPTER_PORT:-3395}" 'SAPIENT adapter'
  fi
  if [[ "${DEMO_CUAS_PROJECTION_MODE:-furia-cuas}" == "furia-cuas" ]]; then
    check_file 'furia-cuas-publisher' "$ROOT/furia-cuas/target/release/furia-cuas-publisher"
  fi
  check_file 's1-sim-server' "$ROOT/S1/target/release/s1-sim-server"
  check_file 'cuas-health-injector' "$ROOT/S1/target/release/cuas-health-injector"
  check_file 'furia-c2 vite' "$ROOT/furia-c2/node_modules/.bin/vite"
fi
printf '\n'
if [[ $fail -eq 0 ]]; then echo 'Golden demo prerequisites look ready.'; else echo 'Golden demo prerequisites are incomplete.'; fi
exit "$fail"
