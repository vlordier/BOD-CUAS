#!/usr/bin/env python3
"""Acceptance monitor for the canonical Bordeaux Core -> S1 -> Core/C2 path."""
from __future__ import annotations

import json
import os
import socket
import time
from urllib.parse import urlparse

NATS_URL = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
SPEED = max(float(os.environ.get("DEMO_SPEED", "4.0")), 0.01)
TIMEOUT = 120.0 / SPEED + 30.0

EXPECTED = {
    "delegation": False,
    "accepted": False,
    "active": False,
    "evidence": False,
    "abort_command": False,
    "abort_result": False,
    "aborted": False,
}


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


def observe(subject: str, payload: dict) -> None:
    if subject == "furia.s1.mission-delegation":
        EXPECTED["delegation"] = (
            payload.get("schema") == "furia.s1.mission-delegation"
            and payload.get("version") == "1.0.0"
            and payload.get("mission_id") == "perimeter_defense_fob"
            and payload.get("authority", {}).get("mode") == "intercept"
            and bool(payload.get("authority", {}).get("authorization_id"))
        )
    elif subject == "furia.s1.execution-progress":
        phase = payload.get("phase")
        if phase == "accepted":
            EXPECTED["accepted"] = True
        elif phase == "active":
            EXPECTED["active"] = True
    elif subject == "furia.s1.execution-evidence":
        EXPECTED["evidence"] = payload.get("state") in {"accepted", "accepted_idempotent", "active"}
    elif subject == "swarm.command.abort":
        EXPECTED["abort_command"] = (
            payload.get("version") == "1.0.0"
            and payload.get("action") == "abort"
            and payload.get("mission_id") == "perimeter_defense_fob"
            and payload.get("policy_id") == "BOD-RWY-FRATRICIDE-003"
            and payload.get("source") == "core-safety-policy"
        )
    elif subject == "swarm.command.result.abort":
        EXPECTED["abort_result"] = payload.get("status") == "executed"
    elif subject == "swarm.fsm.state":
        if payload.get("state") == "Aborted" and payload.get("phase_line") == "SafeHold":
            EXPECTED["aborted"] = True


def main() -> None:
    parsed = urlparse(NATS_URL)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 4222
    deadline = time.monotonic() + TIMEOUT
    buf = bytearray()

    with socket.create_connection((host, port), timeout=10) as sock:
        sock.settimeout(2)
        read_line(sock, buf)
        subjects = [
            "furia.s1.mission-delegation",
            "furia.s1.execution-progress",
            "furia.s1.execution-evidence",
            "swarm.command.abort",
            "swarm.command.result.abort",
            "swarm.fsm.state",
        ]
        commands = [b'CONNECT {"verbose":false,"pedantic":false,"lang":"python-stdlib","version":"1"}\r\n']
        commands.extend(f"SUB {subject} {idx}\r\n".encode() for idx, subject in enumerate(subjects, start=1))
        commands.append(b"PING\r\n")
        sock.sendall(b"".join(commands))

        while time.monotonic() < deadline and not all(EXPECTED.values()):
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
            if len(parts) not in {4, 5}:
                continue
            subject = parts[1].decode()
            size = int(parts[-1])
            raw = read_exact(sock, buf, size)
            if read_exact(sock, buf, 2) != b"\r\n":
                raise RuntimeError("invalid NATS message framing")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            observe(subject, payload)
            print(f"VERIFY {subject}: {payload}", flush=True)

    missing = [name for name, seen in EXPECTED.items() if not seen]
    if missing:
        raise SystemExit(f"Canonical Bordeaux acceptance failed; missing: {', '.join(missing)}")
    print("CANONICAL BORDEAUX ACCEPTANCE: PASS", flush=True)


if __name__ == "__main__":
    main()
