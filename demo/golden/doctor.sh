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
check_dir 'BOD-CUAS' "$ROOT/BOD-CUAS"
check_dir 'furia-core' "$ROOT/furia-core"
check_dir 'furia-ui' "$ROOT/furia-ui"
check_dir 'furia-c2' "$ROOT/furia-c2"
check_dir 'S1' "$ROOT/S1"
check_cmd 'cargo' cargo
check_cmd 'nats' nats
check_cmd 'nats-server' nats-server
check_cmd 'timeout' timeout
check_cmd 'node' node
check_cmd 'pnpm' pnpm
check_cmd 'python3' python3
if command -v docker >/dev/null 2>&1; then printf '%-24s ✅ docker\n' 'container runtime'; elif command -v nats-server >/dev/null 2>&1; then printf '%-24s ✅ nats-server\n' 'NATS runtime'; else printf '%-24s ❌ docker or nats-server\n' 'NATS runtime'; fail=1; fi

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
check_port 4222 'NATS TCP'
check_port 9222 'NATS WebSocket'
check_port 8080 'ATAK dev server'
check_port 3000 'Furia Core'
check_port 3227 'S1 sim server'
check_port 4180 'Furia C2'
printf '\n'
if [[ $fail -eq 0 ]]; then echo 'Golden demo prerequisites look ready.'; else echo 'Golden demo prerequisites are incomplete.'; fi
exit "$fail"
