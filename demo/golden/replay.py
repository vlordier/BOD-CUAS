#!/usr/bin/env python3
"""Deterministic Bordeaux golden-demo event driver using only the NATS wire protocol."""
from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from urllib.parse import urlparse

NATS_URL = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
SPEED = float(os.environ.get("DEMO_SPEED", "1.0"))
ASTERIX_SUBJECT = "surveillance.asterix.record"
MISSION_ID = "perimeter_defense_fob"


def load_asterix_events() -> list[tuple[float, str, dict]]:
    fixtures = json.loads(Path(__file__).with_name("asterix_records.json").read_text(encoding="utf-8"))
    events: list[tuple[float, str, dict]] = []
    for index, fixture in enumerate(fixtures):
        events.append(
            (
                1.0 + index * 0.25,
                ASTERIX_SUBJECT,
                {
                    "category": fixture["category"],
                    "record": fixture["record"],
                    "received_at_ms": 0,
                    "altitude_msl_mm": fixture.get("altitude_msl_mm"),
                    "ground_elevation_msl_mm": fixture.get("ground_elevation_msl_mm"),
                    "_fixture_name": fixture["name"],
                },
            )
        )
    return events


EVENTS = [
    (0.0, "scenario.status", {"id": "bod-cuas-golden", "state": "running", "tick": 0, "elapsed_sec": 0}),
    *load_asterix_events(),
    (20.0, "operator.timeline", {"event": "rogue_uas_detected", "track_id": "uas-rogue-042", "severity": "high"}),
    (30.0, "safety.runway_incursion_predicted", {"track_id": "uas-rogue-042", "runway": "05/23", "eta_s": 37}),
    # The replay never publishes directly to S1. Core consumes this explicit named
    # authorization and creates the bounded/versioned mission delegation.
    (
        35.0,
        "operator.action.authorized",
        {
            "action": "intercept",
            "track_id": "uas-rogue-042",
            "operator": "demo-operator",
            "authorization_id": "bod-demo-auth-042",
            "authorized": True,
        },
    ),
    # This is deliberately the only abort stimulus. Core policy converts it into
    # the canonical swarm.command.abort command.
    (
        80.0,
        "safety.civilian_aircraft_conflict",
        {
            "mission_id": MISSION_ID,
            "flight_id": "AFR762",
            "track_id": "uas-rogue-042",
            "policy": "BOD-RWY-FRATRICIDE-003",
        },
    ),
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
        _ = sock.recv(4096)
        sock.sendall(b'CONNECT {"verbose":false,"pedantic":false,"lang":"python-stdlib","version":"1"}\r\nPING\r\n')
        _ = sock.recv(4096)
        start = time.monotonic()
        for at_s, subject, source_payload in EVENTS:
            deadline = start + at_s / SPEED
            delay = deadline - time.monotonic()
            if delay > 0:
                time.sleep(delay)

            payload = dict(source_payload)
            fixture_name = payload.pop("_fixture_name", None)
            if subject == ASTERIX_SUBJECT:
                payload["received_at_ms"] = int(time.time() * 1000)

            publish(sock, subject, payload)
            sock.sendall(b"PING\r\n")
            _ = sock.recv(4096)
            label = f" ({fixture_name})" if fixture_name else ""
            print(f"[{at_s:05.2f}s] {subject}{label}: {payload}", flush=True)


if __name__ == "__main__":
    main()
