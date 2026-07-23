#!/usr/bin/env python3
"""Self-contained test of the C-UAS golden demo pipeline.

Starts NATS, counter-uas-director, publishes stimuli, and checks results.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import signal
from pathlib import Path
from urllib.parse import urlparse

NATS_URL = "nats://127.0.0.1:4222"
FURIA_ROOT = Path("/Users/vincent/Work")
LOG_DIR = Path(os.environ.get("TMPDIR", "/tmp")) / "furia-bod-golden"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Subjects ────────────────────────────────────────────────────────────
ASTERIX_SUBJECT = "surveillance.asterix.record"
SCENARIO_STATUS_SUBJECT = "scenario.status"
OPERATOR_AUTHORIZED_SUBJECT = "operator.action.authorized"
S1_EXECUTION_HEALTH_SUBJECT = "s1.sim.execution-health"
SAFETY_CIVILIAN_CONFLICT_SUBJECT = "safety.civilian_aircraft_conflict"

# ── NATS helpers ────────────────────────────────────────────────────────
def nats_connect() -> socket.socket:
    parsed = urlparse(NATS_URL)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 4222
    sock = socket.create_connection((host, port), timeout=10)
    sock.settimeout(10)
    _ = sock.recv(4096)  # INFO
    sock.sendall(b'CONNECT {"verbose":false,"pedantic":false}\r\nPING\r\n')
    _ = sock.recv(4096)  # PONG
    return sock

def nats_publish(sock: socket.socket, subject: str, payload: dict) -> None:
    data = json.dumps(payload, separators=(",", ":")).encode()
    sock.sendall(f"PUB {subject} {len(data)}\r\n".encode() + data + b"\r\n")
    sock.sendall(b"PING\r\n")
    _ = sock.recv(4096)

def nats_subscribe(sock: socket.socket, subject: str) -> None:
    sock.sendall(f"SUB {subject} 1\r\n".encode())

def nats_recv(sock: socket.socket, timeout: float = 5.0) -> list[tuple[str, dict]]:
    """Receive NATS messages for up to `timeout` seconds."""
    sock.settimeout(timeout)
    messages: list[tuple[str, dict]] = []
    try:
        while True:
            raw = sock.recv(65536)
            if not raw:
                break
            text = raw.decode("utf-8", errors="replace")
            for line in text.split("\r\n"):
                if line.startswith("MSG "):
                    parts = line.split(" ", 4)
                    if len(parts) >= 4:
                        subj = parts[1]
                        # Try to read payload from subsequent data
                        try:
                            size = int(parts[3])
                            # Payload follows on next recv
                            payload_raw = sock.recv(size + 2)
                            payload = json.loads(payload_raw[:size])
                            messages.append((subj, payload))
                        except (ValueError, json.JSONDecodeError):
                            messages.append((subj, {}))
                elif line.startswith("PING"):
                    sock.sendall(b"PONG\r\n")
    except socket.timeout:
        pass
    return messages

# ── Main test ───────────────────────────────────────────────────────────
def main() -> int:
    print("=" * 60)
    print("  C-UAS GOLDEN DEMO PIPELINE TEST")
    print("=" * 60)
    print()

    # 1. Kill any leftover processes
    print("=== Step 1: Cleanup ===")
    for proc in ["nats-server", "counter-uas-director"]:
        subprocess.run(["pkill", "-f", proc], capture_output=True)
    time.sleep(2)
    print("  Cleanup done")
    print()

    # 2. Start NATS
    print("=== Step 2: Start NATS ===")
    nats_conf = FURIA_ROOT / "BOD-CUAS" / "demo" / "golden" / "nats.conf"
    nats_proc = subprocess.Popen(
        ["nats-server", "-c", str(nats_conf)],
        stdout=(LOG_DIR / "nats.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    time.sleep(2)
    if nats_proc.poll() is not None:
        print(f"  NATS failed to start (exit code {nats_proc.returncode})")
        print((LOG_DIR / "nats.log").read_text())
        return 1
    print(f"  NATS started (PID: {nats_proc.pid})")
    print()

    # 3. Start counter-uas-director
    print("=== Step 3: Start counter-uas-director ===")
    director_bin = FURIA_ROOT / "furia-core" / "target" / "release" / "counter-uas-director"
    env = os.environ.copy()
    env["RUST_LOG"] = "debug"
    director_proc = subprocess.Popen(
        [str(director_bin)],
        stdout=(LOG_DIR / "cuas.log").open("w"),
        stderr=subprocess.STDOUT,
        env=env,
    )
    time.sleep(2)
    if director_proc.poll() is not None:
        print(f"  Director failed to start (exit code {director_proc.returncode})")
        print((LOG_DIR / "cuas.log").read_text())
        nats_proc.terminate()
        return 1
    print(f"  Director started (PID: {director_proc.pid})")
    print()

    # 4. Subscribe to canonical events
    print("=== Step 4: Subscribe to canonical events ===")
    sub_sock = nats_connect()
    for subj in [
        "surveillance.observation",
        "furia.s1.mission-delegation",
        "swarm.command.abort",
        "cuas.risk.protected_volume",
        "cuas.incident.state",
    ]:
        nats_subscribe(sub_sock, subj)
    print("  Subscribed to canonical event subjects")
    print()

    # 5. Publish ASTERIX records
    print("=== Step 5: Publish ASTERIX records ===")
    pub_sock = nats_connect()
    fixtures = json.loads((FURIA_ROOT / "BOD-CUAS" / "demo" / "golden" / "asterix_records.json").read_text())
    for i, fixture in enumerate(fixtures):
        payload = {
            "category": fixture["category"],
            "record": fixture["record"],
            "received_at_ms": int(time.time() * 1000),
            "altitude_msl_mm": fixture.get("altitude_msl_mm"),
            "ground_elevation_msl_mm": fixture.get("ground_elevation_msl_mm"),
        }
        nats_publish(pub_sock, ASTERIX_SUBJECT, payload)
        print(f"  [{i+1}/{len(fixtures)}] Published CAT{fixture['category']}: {fixture['name']}")
        time.sleep(0.25)
    print()

    # 6. Publish CAT062 with velocity for track 4660
    print("=== Step 6: Publish CAT062 with velocity ===")
    cat062_record = [
        0x9B, 0x08,  # FSPEC: FRN1,4,5,7,12
        1, 2,         # FRN1: SAC=1, SIC=2
        0x00, 0x13, 0x00,  # FRN4: Time=38s
        0x1F, 0xE0, 0xBE, 0x33, 0xFF, 0x7D, 0xBA, 0x9F,  # FRN5: WGS84 position
        0x27, 0x10, 0xEC, 0x78,  # FRN7: vx=10m/s, vy=-5m/s
        0x12, 0x34,  # FRN12: Track Number=4660
    ]
    nats_publish(pub_sock, ASTERIX_SUBJECT, {
        "category": 62,
        "record": cat062_record,
        "received_at_ms": int(time.time() * 1000),
        "altitude_msl_mm": 50_000,
        "ground_elevation_msl_mm": None,
    })
    print("  Published CAT062 for track 4660 with velocity")
    time.sleep(1)
    print()

    # 7. Check for surveillance observations
    print("=== Step 7: Check surveillance observations ===")
    msgs = nats_recv(sub_sock, 2.0)
    obs_found = any(s == "surveillance.observation" for s, _ in msgs)
    if obs_found:
        print("  ✅ surveillance.observation received")
    else:
        print("  ⚠️  No surveillance.observation received (may be expected)")
    print()

    # 8. Publish operator authorization
    print("=== Step 8: Publish operator authorization ===")
    nats_publish(pub_sock, OPERATOR_AUTHORIZED_SUBJECT, {
        "action": "intercept",
        "track_id": "4660",
        "operator": "demo-operator",
        "authorization_id": "bod-demo-auth-4660",
        "authorized": True,
    })
    print("  Published operator authorization for track 4660")
    time.sleep(2)
    print()

    # 9. Check for delegation
    print("=== Step 9: Check for mission delegation ===")
    msgs = nats_recv(sub_sock, 3.0)
    delegation_found = any(s == "furia.s1.mission-delegation" for s, _ in msgs)
    if delegation_found:
        print("  ✅ furia.s1.mission-delegation received")
    else:
        print("  ❌ No mission delegation received")
        # Check director log for rejection reason
        log = (LOG_DIR / "cuas.log").read_text()
        if "Rejecting" in log:
            for line in log.split("\n"):
                if "Rejecting" in line:
                    print(f"  Director log: {line}")
    print()

    # 10. Publish safety conflict
    print("=== Step 10: Publish safety conflict ===")
    nats_publish(pub_sock, SAFETY_CIVILIAN_CONFLICT_SUBJECT, {
        "mission_id": "perimeter_defense_fob",
        "flight_id": "AFR762",
        "track_id": "4660",
        "policy": "BOD-RWY-FRATRICIDE-003",
    })
    print("  Published civilian aircraft safety conflict")
    time.sleep(2)
    print()

    # 11. Check for abort command
    print("=== Step 11: Check for abort command ===")
    msgs = nats_recv(sub_sock, 3.0)
    abort_found = any(s == "swarm.command.abort" for s, _ in msgs)
    if abort_found:
        print("  ✅ swarm.command.abort received")
    else:
        print("  ❌ No abort command received")
    print()

    # 12. Cleanup
    print("=== Step 12: Cleanup ===")
    director_proc.terminate()
    director_proc.wait()
    nats_proc.terminate()
    nats_proc.wait()
    pub_sock.close()
    sub_sock.close()
    print("  Processes terminated")
    print()

    # Summary
    print("=" * 60)
    if delegation_found and abort_found:
        print("  ✅ PIPELINE TEST: PASS")
        print("=" * 60)
        return 0
    else:
        print("  ❌ PIPELINE TEST: FAIL")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())