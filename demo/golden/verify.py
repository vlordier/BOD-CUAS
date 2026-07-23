#!/usr/bin/env python3
"""Golden demo acceptance verifier — monitors canonical Core-admitted event stream.

Subscribes to NATS and verifies causal ordering of the Bordeaux C-UAS scenario.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse

NATS_URL = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
TIMEOUT_SEC = float(os.environ.get("VERIFY_TIMEOUT", "120"))

# Subjects we monitor for causal ordering
SUBJECTS = [
    "scenario.status",
    "furia.s1.mission-delegation",
    "swarm.command.abort",
]


def main() -> int:
    parsed = urlparse(NATS_URL)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 4222

    # Use nats sub --count to exit cleanly after receiving expected messages
    # Expected: 2x scenario.status + 1x delegation + 1x abort = 4
    sub_cmd = ["nats", "sub", "-s", NATS_URL, "--count", "4"] + SUBJECTS

    print(f"verify.py: monitoring {len(SUBJECTS)} subjects on {NATS_URL}", flush=True)

    proc = subprocess.Popen(
        sub_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    first_seen: dict[str, float] = {}
    start = time.monotonic()
    passed = True
    errors: list[str] = []
    risk_seen = False
    incident_seen = False
    delegation_seen = False
    evidence_seen = False
    abort_command_seen = False
    abort_result_seen = False

    try:
        for line in proc.stdout or []:
            if time.monotonic() - start > TIMEOUT_SEC:
                break
            if line.startswith("[#"):
                # Parse: [#1] Received on "subject"
                if 'Received on "' in line:
                    subj = line.split('Received on "')[1].split('"')[0]
                    now = time.monotonic()
                    if subj not in first_seen:
                        first_seen[subj] = now

                    if subj == "scenario.status":
                        print(f"  ✓ SCENARIO STATUS observed", flush=True)
                    elif subj == "furia.s1.mission-delegation":
                        delegation_seen = True
                        print(f"  ✓ MISSION DELEGATION observed", flush=True)
                    elif subj == "swarm.command.abort":
                        abort_command_seen = True
                        print(f"  ✓ ABORT COMMAND observed", flush=True)
    except Exception as e:
        print(f"verify.py: error: {e}", flush=True)
    finally:
        proc.terminate()
        proc.wait()

    # Causal ordering checks
    if delegation_seen:
        print("  ✓ Causal: delegation observed", flush=True)
    else:
        errors.append("FAIL: no mission delegation observed")
        passed = False

    if abort_command_seen:
        print("  ✓ Causal: abort command observed", flush=True)
    else:
        errors.append("FAIL: no abort command observed")
        passed = False

    # Check ordering: delegation should come before abort
    if delegation_seen and abort_command_seen:
        del_t = first_seen.get("furia.s1.mission-delegation", 0)
        cmd_t = first_seen.get("swarm.command.abort", 0)
        if del_t > cmd_t:
            errors.append("FAIL: delegation not before abort command")
            passed = False
        else:
            print("  ✓ Causal: delegation < abort command", flush=True)

    print("", flush=True)
    if passed:
        print("=== verify.py: PASS ===", flush=True)
        return 0
    else:
        for err in errors:
            print(err, flush=True)
        print("=== verify.py: FAIL ===", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())