#!/usr/bin/env python3
"""Verify bounded comm-denied continuation and recovery via Core-admitted S1 evidence."""
from __future__ import annotations

import json
import os
import socket
import time
from urllib.parse import urlparse

NATS_URL = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
SPEED = max(float(os.environ.get("DEMO_SPEED", "4.0")), 0.01)
TIMEOUT = 85.0 / SPEED + 25.0
MISSION_ID = "perimeter_defense_fob"


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
    out = bytes(buf[:size])
    del buf[:size]
    return out


def main() -> None:
    parsed = urlparse(NATS_URL)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 4222
    deadline = time.monotonic() + TIMEOUT
    buf = bytearray()
    contract_id: str | None = None
    lost_link_at: int | None = None
    recovered_at: int | None = None

    with socket.create_connection((host, port), timeout=10) as sock:
        sock.settimeout(2)
        read_line(sock, buf)
        sock.sendall(
            b'CONNECT {"verbose":false,"pedantic":false,"lang":"python-stdlib","version":"1"}\r\n'
            b"SUB cuas.mission.delegation 1\r\n"
            b"SUB cuas.execution.evidence 2\r\n"
            b"PING\r\n"
        )
        while time.monotonic() < deadline and recovered_at is None:
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
            subject = parts[1].decode()
            size = int(parts[-1])
            payload = json.loads(read_exact(sock, buf, size))
            if read_exact(sock, buf, 2) != b"\r\n":
                raise RuntimeError("invalid NATS framing")

            if subject == "cuas.mission.delegation" and payload.get("mission_id") == MISSION_ID:
                contract_id = payload.get("correlation_id")
            elif subject == "cuas.execution.evidence" and contract_id and payload.get("contract_id") == contract_id:
                observed = int(payload.get("observed_at_ms", 0))
                if (
                    payload.get("state") == "active"
                    and payload.get("degraded_mode") == "lost_link_continuation"
                    and payload.get("rejection_reason") is None
                    and int(payload.get("contract_remaining_ms", 0)) > 0
                ):
                    lost_link_at = observed
                elif (
                    lost_link_at is not None
                    and observed > lost_link_at
                    and payload.get("state") == "active"
                    and payload.get("degraded_mode") == "normal"
                    and payload.get("rejection_reason") is None
                ):
                    recovered_at = observed

    if not contract_id:
        raise SystemExit("Comm-denied acceptance failed: no authoritative delegation observed")
    if lost_link_at is None:
        raise SystemExit("Comm-denied acceptance failed: no bounded lost_link_continuation evidence")
    if recovered_at is None:
        raise SystemExit("Comm-denied acceptance failed: no normal recovery evidence after lost link")
    print("COMM-DENIED ACCEPTANCE: PASS", flush=True)


if __name__ == "__main__":
    main()
