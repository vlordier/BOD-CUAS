#!/usr/bin/env bash

# Shared deployment knobs for doctor.sh and run.sh. Scenario data and
# authority contracts remain in the versioned replay fixtures.

load_demo_runtime_config() {
  NATS_TCP_PORT="${DEMO_NATS_TCP_PORT:-4222}"
  NATS_WS_PORT="${DEMO_NATS_WS_PORT:-9222}"
  SAPIENT_ADAPTER_PORT="${DEMO_SAPIENT_ADAPTER_PORT:-3395}"
  CORE_PORT="${DEMO_CORE_PORT:-3000}"
  S1_PORT="${DEMO_S1_PORT:-3227}"
  C2_PORT="${DEMO_C2_PORT:-4180}"
  ATAK_PORT="${DEMO_ATAK_PORT:-8080}"
  SAPIENT_PATH="${DEMO_SAPIENT_PATH:-direct}"
  CUAS_PROJECTION_MODE="${DEMO_CUAS_PROJECTION_MODE:-furia-cuas}"
  NATS_URL="${NATS_URL:-nats://127.0.0.1:$NATS_TCP_PORT}"
  VITE_NATS_WS_URL="${VITE_NATS_WS_URL:-ws://127.0.0.1:$NATS_WS_PORT}"
}

validate_demo_runtime_config() {
  local name
  for name in NATS_TCP_PORT NATS_WS_PORT SAPIENT_ADAPTER_PORT CORE_PORT S1_PORT C2_PORT ATAK_PORT; do
    if [[ ! "${!name}" =~ ^[0-9]+$ ]] || (( ${!name} < 1 || ${!name} > 65535 )); then
      echo "ERROR: $name must be a TCP port between 1 and 65535" >&2
      return 2
    fi
  done
  if [[ "$SAPIENT_PATH" != "direct" && "$SAPIENT_PATH" != "protobuf-adapter" ]]; then
    echo "ERROR: DEMO_SAPIENT_PATH must be direct or protobuf-adapter" >&2
    return 2
  fi
  if [[ "$CUAS_PROJECTION_MODE" != "furia-cuas" && "$CUAS_PROJECTION_MODE" != "compatibility" ]]; then
    echo "ERROR: DEMO_CUAS_PROJECTION_MODE must be furia-cuas or compatibility" >&2
    return 2
  fi
  if [[ "$SAPIENT_PATH" == "protobuf-adapter" && "$CUAS_PROJECTION_MODE" != "furia-cuas" ]]; then
    echo "ERROR: protobuf-adapter requires DEMO_CUAS_PROJECTION_MODE=furia-cuas" >&2
    return 2
  fi
  if [[ -n "${DEMO_NATS_MODE:-}" && "${DEMO_NATS_MODE}" != "auto" && "${DEMO_NATS_MODE}" != "local" && "${DEMO_NATS_MODE}" != "external" && "${DEMO_NATS_MODE}" != "headless" ]]; then
    echo "ERROR: DEMO_NATS_MODE must be auto, local, external, or headless" >&2
    return 2
  fi
  local left right
  # Every listener is part of the same local deployment, including the
  # broker and optional ATAK bridge. Reject collisions up front so a skipped
  # process cannot hide a configuration that will fail when the feature is
  # enabled later.
  local runtime_ports=(
    NATS_TCP_PORT NATS_WS_PORT SAPIENT_ADAPTER_PORT CORE_PORT
    S1_PORT C2_PORT ATAK_PORT
  )
  for left in "${runtime_ports[@]}"; do
    for right in "${runtime_ports[@]}"; do
      [[ "$left" < "$right" ]] || continue
      if [[ "${!left}" == "${!right}" ]]; then
        echo "ERROR: $left and $right cannot share port ${!left}" >&2
        return 2
      fi
    done
  done
}

