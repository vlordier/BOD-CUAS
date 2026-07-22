#!/usr/bin/env python3
"""Fail-closed acceptance monitor for the Bordeaux golden demo."""
from __future__ import annotations

import json
import os
import socket
import time
from urllib.parse import urlparse

NATS_URL = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
SPEED = max(float(os.environ.get("DEMO_SPEED", "4.0")), 0.01)
TIMEOUT = 120.0 / SPEED + 30.0
MISSION_ID = "perimeter_defense_fob"
ROGUE_TRACK_ID = "4660"
AUTHORIZATION_ID = "bod-demo-auth-4660"

EXPECTED = {
    "delegation_emitted": False,
    "delegation_projected": False,
    "delegation_accepted": False,
    "execution_evidence": False,
    "executing": False,
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


def valid_delegation(payload: dict) -> bool:
    constraints = payload.get("cuas_constraints") or {}
    target = constraints.get("target") or {}
    velocity = target.get("velocity_ned_mm_s")
    tasks = payload.get("graph", {}).get("tasks") or []
    first_task = tasks[0] if tasks else {}
    return (
        payload.get("schema") == "furia.s1.mission-delegation"
        and payload.get("version") == "1.0.0"
        and payload.get("mission_id") == MISSION_ID
        and payload.get("plan_revision") == 1
        and payload.get("authority", {}).get("mode") == "intercept"
        and payload.get("authority", {}).get("authorization_id") == AUTHORIZATION_ID
        and target.get("track_id") == ROGUE_TRACK_ID
        and isinstance(velocity, list)
        and len(velocity) == 3
        and any(component != 0 for component in velocity)
        and target.get("cooperative") is False
        and target.get("authorized") is False
        and first_task.get("is_lethal") is False
    )


def observe(subject: str, payload: dict) -> None:
    if subject == "furia.s1.mission-delegation":
        EXPECTED["delegation_emitted"] = valid_delegation(payload)
    elif subject == "cuas.mission.delegation":
        EXPECTED["delegation_projected"] = valid_delegation(payload)
    elif subject == "furia.s1.execution-progress":
        if payload.get("mission_id") == MISSION_ID and payload.get("phase") in {"accepted", "active"}:
            EXPECTED["delegation_accepted"] = True
    elif subject == "cuas.execution.evidence":
        EXPECTED["execution_evidence"] = (
            payload.get("plan_revision") == 1
            and payload.get("state") in {"accepted", "active", "safe_hold", "aborted"}
            and payload.get("degraded_mode") in {
                "normal",
                "stale_remote_tracks",
                "degraded_navigation",
                "degraded_communications",
                "lost_link_continuation",
                "safety_hold",
                "return_to_launch",
            }
            and isinstance(payload.get("contract_remaining_ms"), int)
            and payload.get("contract_remaining_ms", -1) >= 0
            and isinstance(payload.get("track_age_ms"), int)
            and payload.get("track_age_ms", -1) >= 0
        )
    elif subject == "swarm.command.abort":
        EXPECTED["abort_command"] = (
            payload.get("version") == "1.0.0"
            and payload.get("action") == "abort"
            and payload.get("mission_id") == MISSION_ID
            and payload.get("policy_id") == "BOD-RWY-FRATRICIDE-003"
            and payload.get("source") == "core-safety-policy"
        )
    elif subject == "swarm.command.result.abort":
        EXPECTED["abort_result"] = payload.get("mission_id") == MISSION_ID and payload.get("status") == "executed"
    elif subject == "swarm.fsm.state":
        state = payload.get("state")
        if payload.get("mission_id") == MISSION_ID and state == "ExecutingOpord":
            EXPECTED["executing"] = True
        if payload.get("mission_id") == MISSION_ID and state == "Aborted" and payload.get("phase_line") == "SafeHold":
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
        sock.sendall(
            b'CONNECT {"verbose":false,"pedantic":false,"lang":"python-stdlib","version":"1"}\r\n'
            b"SUB furia.s1.mission-delegation 1\r\n"
            b"SUB furia.s1.execution-progress 2\r\n"
            b"SUB swarm.fsm.state 3\r\n"
            b"SUB swarm.command.abort 4\r\n"
            b"SUB swarm.command.result.abort 5\r\n"
            b"SUB cuas.mission.delegation 6\r\n"
            b"SUB cuas.execution.evidence 7\r\n"
            b"PING\r\n"
        )

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
            trailer = read_exact(sock, buf, 2)
            if trailer != b"\r\n":
                raise RuntimeError("invalid NATS message framing")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            observe(subject, payload)
            print(f"VERIFY {subject}: {payload}", flush=True)

    missing = [name for name, seen in EXPECTED.items() if not seen]
    if missing:
        raise SystemExit(f"Golden demo acceptance failed; missing: {', '.join(missing)}")
    print("GOLDEN DEMO ACCEPTANCE: PASS", flush=True)


if __name__ == "__main__":
    main()
