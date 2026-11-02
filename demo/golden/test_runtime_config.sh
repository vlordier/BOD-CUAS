#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/runtime-config.sh"

assert_valid() {
  load_demo_runtime_config
  validate_demo_runtime_config >/dev/null
}

assert_invalid() {
  if validate_demo_runtime_config >/dev/null 2>&1; then
    echo "expected invalid runtime configuration to fail" >&2
    exit 1
  fi
}

DEMO_NATS_TCP_PORT=4322 DEMO_NATS_WS_PORT=9322 DEMO_SAPIENT_ADAPTER_PORT=3495 \
  DEMO_CORE_PORT=3300 DEMO_S1_PORT=3327 DEMO_C2_PORT=4380 DEMO_ATAK_PORT=8088 \
  DEMO_SAPIENT_PATH=protobuf-adapter DEMO_CUAS_PROJECTION_MODE=furia-cuas \
  assert_valid

NATS_TCP_PORT=0
assert_invalid

NATS_TCP_PORT=4222
SAPIENT_ADAPTER_PORT=3000
CORE_PORT=3000
S1_PORT=3227
C2_PORT=4180
ATAK_PORT=8080
SAPIENT_PATH=direct
CUAS_PROJECTION_MODE=furia-cuas
assert_invalid

NATS_TCP_PORT=4222
SAPIENT_ADAPTER_PORT=3395
CORE_PORT=3000
S1_PORT=3227
C2_PORT=4180
ATAK_PORT=8080
SAPIENT_PATH=protobuf-adapter
CUAS_PROJECTION_MODE=compatibility
assert_invalid

NATS_TCP_PORT=4222
NATS_WS_PORT=9222
SAPIENT_ADAPTER_PORT=3395
CORE_PORT=3000
S1_PORT=3227
C2_PORT=4180
ATAK_PORT=3000
SAPIENT_PATH=direct
CUAS_PROJECTION_MODE=furia-cuas
assert_invalid

DEMO_NATS_MODE=unsupported
assert_invalid

echo 'runtime configuration tests: passed'
