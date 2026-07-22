#!/usr/bin/env python3
"""Fail-closed monitor for Core-owned threat-origin/emitter outputs in the Bordeaux demo."""
from __future__ import annotations

import json
import os
import socket
import time
from urllib.parse import urlparse

NATS_URL = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
SPEED = max(float(os.environ.get("DEMO_SPEED", "4.0")), 0.01)
TIMEOUT = 50.0 / SPEED + 20.0
ROGUE_TRACK_ID = "4660"


def read_line(sock: socket.socket, buf: bytearray) -> bytes:
    while True:
        marker = buf.find(b"\r\n")
        if marker >= 0:
            line = bytes(buf[:marker])
            del buf[: marker + 2]
            return line
        chunk = sock.recv(65536)
        if not chunk:
            raise ConnectionError("NATS connection closed")
        buf.extend(chunk)


def read_exact(sock: socket.socket, buf: bytearray, size: int) -> bytes:
    while len(buf) < size:
        chunk = sock.recv(65536)
        if not chunk:
            raise ConnectionError("NATS connection closed")
        buf.extend(chunk)
    data = bytes(buf[:size])
    del buf[:size]
    return data


def valid_geo(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    major = value.get("uncertainty_major_mm")
    minor = value.get("uncertainty_minor_mm")
    confidence = value.get("confidence_permille")
    return (
        isinstance(value.get("latitude_e7"), int)
        and isinstance(value.get("longitude_e7"), int)
        and isinstance(major, int)
        and isinstance(minor, int)
        and major >= minor > 0
        and isinstance(confidence, int)
        and 0 <= confidence <= 1000
    )


def main() -> None:
    parsed = urlparse(NATS_URL)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 4222
    deadline = time.monotonic() + TIMEOUT
    buf = bytearray()
    emitter_seen = False
    origin_seen = False
    delegation_seen = False

    with socket.create_connection((host, port), timeout=10) as sock:
        sock.settimeout(2)
        read_line(sock, buf)
        sock.sendall(
            b'CONNECT {"verbose":false,"pedantic":false,"lang":"python-stdlib","version":"1"}\r\n'
            b"SUB cuas.emitter.localization 1\r\n"
            b"SUB cuas.threat.origin 2\r\n"
            b"SUB furia.s1.mission-delegation 3\r\n"
            b"PING\r\n"
        )
        while time.monotonic() < deadline and not delegation_seen:
            try:
                line = read_line(sock, buf)
            except (TimeoutError, socket.timeout):
                continue
            if line == b"PING":
                sock.sendall(b"PONG\r\n")
                continue
            if line in {b"PONG", b"+OK"} or line.startswith(b"INFO "):
                continue
            if line.startswith(b"-ERR"):
                raise RuntimeError(line.decode(errors="replace"))
            if not line.startswith(b"MSG "):
                continue
            parts = line.split()
            size = int(parts[-1])
            subject = parts[1].decode()
            raw = read_exact(sock, buf, size)
            if read_exact(sock, buf, 2) != b"\r\n":
                raise RuntimeError("invalid NATS framing")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if subject == "cuas.emitter.localization":
                evidence = payload.get("evidence") or []
                methods = set(payload.get("methods") or [])
                emitter_seen = emitter_seen or (
                    payload.get("associated_track_id") == ROGUE_TRACK_ID
                    and payload.get("emitter_id") == "RF-12"
                    and valid_geo(payload.get("estimate"))
                    and "fused" in methods
                    and any(isinstance(item, dict) and item.get("kind") == "rf_bearing" for item in evidence)
                )
            elif subject == "cuas.threat.origin":
                hypotheses = payload.get("launch_hypotheses") or []
                probability_mass = sum(
                    item.get("probability_permille", 0) for item in hypotheses if isinstance(item, dict)
                )
                origin_seen = origin_seen or (
                    payload.get("track_id") == ROGUE_TRACK_ID
                    and payload.get("associated_emitter_id") == "RF-12"
                    and valid_geo(payload.get("controller_estimate"))
                    and len(hypotheses) >= 1
                    and probability_mass <= 1000
                    and all(valid_geo(item.get("estimate")) for item in hypotheses if isinstance(item, dict))
                )
            elif subject == "furia.s1.mission-delegation" and payload.get("mission_id") == "perimeter_defense_fob":
                delegation_seen = True
                if not (emitter_seen and origin_seen):
                    raise SystemExit("Origin acceptance failed: Core delegated before valid emitter + launch-origin evidence")

    if not delegation_seen:
        raise SystemExit("Origin acceptance failed: delegation not observed")
    if not emitter_seen or not origin_seen:
        raise SystemExit("Origin acceptance failed: missing valid Core-owned origin outputs")
    print("THREAT ORIGIN ACCEPTANCE: PASS", flush=True)


if __name__ == "__main__":
    main()
