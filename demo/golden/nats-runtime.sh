#!/usr/bin/env bash

create_demo_nats_state_dir() {
  mktemp -d "${TMPDIR:-/tmp}/furia-bod-golden.XXXXXXXX"
}

render_demo_nats_config() {
  local template="$1" output="$2" state_dir="$3" tcp_port="$4" websocket_port="$5"
  local store_dir="$state_dir/jetstream"
  local escaped_store_dir
  escaped_store_dir="$(printf '%s' "$store_dir" | sed 's/[&|\\]/\\&/g')"

  mkdir -p "$store_dir"
  sed \
    -e "s/^port: 4222$/port: $tcp_port/" \
    -e "s/^  port: 9222$/  port: $websocket_port/" \
    -e "s|^  store_dir:.*|  store_dir: \"$escaped_store_dir\"|" \
    "$template" >"$output"
}
