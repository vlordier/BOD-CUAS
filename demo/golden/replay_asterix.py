#!/usr/bin/env python3
"""Replay deterministic Bordeaux ASTERIX records into the Core ingress subject.

Uses the NATS core protocol directly so the golden demo does not require a Python
NATS package or the `nats` CLI. JetStream persistence is provided by the server
stream configuration; Core consumes the same `surveillance.asterix.record` subject.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

SUBJECT = "surveillance.asterix.record"


def nats_endpoint() -> tuple[str, int]:
    raw = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
    parsed = urlparse(raw)
    if parsed.scheme not in {"nats", ""}:
        raise ValueError(f"unsupported NATS_URL scheme for demo replay: {parsed.scheme}")
    return parsed.hostname or "127.0.0.1", parsed.port or 4222


def publish(sock: socket.socket, payload: bytes) -> None:
    header = f"PUB {SUBJECT} {len(payload)}\r\n".encode()
    sock.sendall(header + payload + b"\r\n")


def flush(sock: socket.socket) -> None:
    sock.sendall(b"PING\r\n")
    deadline = time.monotonic() + 2.0
    data = b""
    while time.monotonic() < deadline:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
        if b"PONG\r\n" in data:
            return
    raise RuntimeError("NATS did not acknowledge replay flush")


def main() -> int:
    fixture_path = Path(__file__).with_name("asterix_records.json")
    fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))
    host, port = nats_endpoint()

    with socket.create_connection((host, port), timeout=5.0) as sock:
        sock.settimeout(2.0)
        # Consume the INFO line, then enter normal client mode.
        first = sock.recv(4096)
        if b"INFO " not in first:
            raise RuntimeError("NATS server did not send INFO greeting")
        sock.sendall(b'CONNECT {"verbose":false,"pedantic":false,"lang":"python","version":"bod-golden-v1"}\r\n')

        for fixture in fixtures:
            envelope = {
                "category": fixture["category"],
                "record": fixture["record"],
                "received_at_ms": int(time.time() * 1000),
                "altitude_msl_mm": fixture.get("altitude_msl_mm"),
                "ground_elevation_msl_mm": fixture.get("ground_elevation_msl_mm"),
            }
            payload = json.dumps(envelope, separators=(",", ":")).encode()
            publish(sock, payload)
            print(f"published {fixture['name']}: CAT{fixture['category']:03d}")
            time.sleep(0.15)

        flush(sock)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ASTERIX replay failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
