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
check_cmd 'node' node
check_cmd 'pnpm' pnpm
check_cmd 'python3' python3
if command -v docker >/dev/null 2>&1; then printf '%-24s ✅ docker\n' 'container runtime'; elif command -v nats-server >/dev/null 2>&1; then printf '%-24s ✅ nats-server\n' 'NATS runtime'; else printf '%-24s ❌ docker or nats-server\n' 'NATS runtime'; fail=1; fi
printf '\n'
if [[ $fail -eq 0 ]]; then echo 'Golden demo prerequisites look ready.'; else echo 'Golden demo prerequisites are incomplete.'; fi
exit "$fail"
