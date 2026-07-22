#!/usr/bin/env bash
set -euo pipefail
ROOT="${FURIA_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fail=0
check_dir() {
  local name="$1" path="$2"
  if [[ -d "$path" ]]; then printf '%-28s ✅ %s\n' "$name" "$path"; else printf '%-28s ❌ %s\n' "$name" "$path"; fail=1; fi
}
check_file() {
  local name="$1" path="$2"
  if [[ -f "$path" ]]; then printf '%-28s ✅ %s\n' "$name" "$path"; else printf '%-28s ❌ %s\n' "$name" "$path"; fail=1; fi
}
check_cmd() {
  local name="$1" cmd="$2"
  if command -v "$cmd" >/dev/null 2>&1; then printf '%-28s ✅ %s\n' "$name" "$cmd"; else printf '%-28s ❌ %s\n' "$name" "$cmd"; fail=1; fi
}
check_port_free() {
  local port="$1" label="$2"
  if python3 - "$port" <<'PY'
import socket, sys
port = int(sys.argv[1])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind(("127.0.0.1", port))
except OSError:
    raise SystemExit(1)
finally:
    s.close()
PY
  then printf '%-28s ✅ %s\n' "$label" "$port"; else printf '%-28s ❌ %s already in use\n' "$label" "$port"; fail=1; fi
}
check_git_repo() {
  local name="$1" path="$2"
  if git -C "$path" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    local branch sha dirty=""
    branch="$(git -C "$path" branch --show-current 2>/dev/null || true)"
    sha="$(git -C "$path" rev-parse --short HEAD 2>/dev/null || true)"
    [[ -n "$(git -C "$path" status --porcelain 2>/dev/null || true)" ]] && dirty=" DIRTY"
    printf '%-28s ✅ %s@%s%s\n' "$name" "${branch:-detached}" "$sha" "$dirty"
  else
    printf '%-28s ❌ not a git checkout: %s\n' "$name" "$path"
    fail=1
  fi
}

printf 'Furia Bordeaux golden demo doctor\n\n'
check_dir 'BOD-CUAS' "$ROOT/BOD-CUAS"
check_dir 'furia-core' "$ROOT/furia-core"
check_dir 'furia-ui' "$ROOT/furia-ui"
check_dir 'furia-c2' "$ROOT/furia-c2"
check_dir 'S1' "$ROOT/S1"

printf '\nRequired demo files\n'
check_file 'NATS config' "$SCRIPT_DIR/nats.conf"
check_file 'ASTERIX fixtures' "$SCRIPT_DIR/asterix_records.json"
check_file 'authorization policy' "$ROOT/BOD-CUAS/config/cuas-authorizations.yaml"
check_file 'protected volumes' "$SCRIPT_DIR/protected-volumes.yaml"
check_file 'golden verifier' "$SCRIPT_DIR/verify.py"
check_file 'origin verifier' "$SCRIPT_DIR/verify_origin.py"
check_file 'comm-denied verifier' "$SCRIPT_DIR/verify_comm_denied.py"
check_file 'threat-origin profile' "$SCRIPT_DIR/threat-origin.yaml"
check_file 'S1 health injector source' "$ROOT/S1/tools/s1-sim-server/src/bin/cuas-health-injector.rs"
check_file 'C2 package manifest' "$ROOT/furia-c2/package.json"
check_file 'private UI dependency' "$ROOT/furia-ui/packages/ui/package.json"
check_file 'Core workspace' "$ROOT/furia-core/Cargo.toml"
check_file 'S1 workspace' "$ROOT/S1/Cargo.toml"

printf '\nToolchain\n'
check_cmd 'git' git
check_cmd 'cargo' cargo
check_cmd 'node' node
check_cmd 'pnpm' pnpm
check_cmd 'python3' python3
check_cmd 'curl' curl
if command -v docker >/dev/null 2>&1; then printf '%-28s ✅ docker\n' 'NATS runtime'; elif command -v nats-server >/dev/null 2>&1; then printf '%-28s ✅ nats-server\n' 'NATS runtime'; else printf '%-28s ❌ docker or nats-server\n' 'NATS runtime'; fail=1; fi

if command -v git >/dev/null 2>&1; then
  printf '\nRepository revisions\n'
  check_git_repo 'BOD-CUAS revision' "$ROOT/BOD-CUAS"
  check_git_repo 'furia-core revision' "$ROOT/furia-core"
  check_git_repo 'furia-ui revision' "$ROOT/furia-ui"
  check_git_repo 'furia-c2 revision' "$ROOT/furia-c2"
  check_git_repo 'S1 revision' "$ROOT/S1"
fi

if command -v python3 >/dev/null 2>&1; then
  printf '\nRequired ports\n'
  check_port_free 4222 'NATS TCP'
  check_port_free 9222 'NATS WebSocket'
  check_port_free 8080 'ATAK dev server'
  check_port_free 3000 'Furia Core'
  check_port_free 3227 'S1 sim server'
  check_port_free 5173 'Furia C2'
fi
printf '\n'
if [[ $fail -eq 0 ]]; then echo 'Golden demo prerequisites look ready.'; else echo 'Golden demo prerequisites are incomplete.'; fi
exit "$fail"
