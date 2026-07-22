#!/usr/bin/env python3
"""Deterministic Bordeaux golden-demo event driver using only the NATS wire protocol."""
from __future__ import annotations

import json
import os
import socket
import time
from urllib.parse import urlparse

NATS_URL = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
SPEED = float(os.environ.get("DEMO_SPEED", "1.0"))

EVENTS = [
    (0.0, "scenario.status", {"id": "bod-cuas-golden", "state": "running", "tick": 0, "elapsed_sec": 0}),
    (20.0, "operator.timeline", {"event": "rogue_uas_detected", "track_id": "uas-rogue-042", "severity": "high"}),
    (30.0, "safety.runway_incursion_predicted", {"track_id": "uas-rogue-042", "runway": "05/23", "eta_s": 37}),
    (35.0, "swarm.intent.submit", {"scenario_id": "perimeter_defense_fob", "intent": "Counter-UAS intercept and contain rogue UAS approaching Bordeaux runway 05/23"}),
    (45.0, "operator.action.authorized", {"action": "intercept", "track_id": "uas-rogue-042", "operator": "demo-operator", "authorized": True}),
    # This is deliberately the only abort stimulus. Core policy converts this
    # safety evidence into the canonical swarm.command.abort command.
    (80.0, "safety.civilian_aircraft_conflict", {
        "mission_id": "perimeter_defense_fob",
        "flight_id": "AFR762",
        "track_id": "uas-rogue-042",
        "policy": "BOD-RWY-FRATRICIDE-003",
    }),
    (95.0, "scenario.status", {"id": "bod-cuas-golden", "state": "complete", "tick": 95, "elapsed_sec": 95}),
]


def publish(sock: socket.socket, subject: str, payload: dict) -> None:
    data = json.dumps(payload, separators=(",", ":")).encode()
    sock.sendall(f"PUB {subject} {len(data)}\r\n".encode() + data + b"\r\n")


def main() -> None:
    parsed = urlparse(NATS_URL)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 4222
    with socket.create_connection((host, port), timeout=10) as sock:
        sock.settimeout(10)
        _ = sock.recv(4096)  # INFO
        sock.sendall(b'CONNECT {"verbose":false,"pedantic":false,"lang":"python-stdlib","version":"1"}\r\nPING\r\n')
        _ = sock.recv(4096)
        start = time.monotonic()
        for at_s, subject, payload in EVENTS:
            deadline = start + at_s / SPEED
            delay = deadline - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            publish(sock, subject, payload)
            sock.sendall(b"PING\r\n")
            _ = sock.recv(4096)
            print(f"[{at_s:05.1f}s] {subject}: {payload}", flush=True)


if __name__ == "__main__":
    main()
