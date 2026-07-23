#!/usr/bin/env python3
"""Threat-origin/emitter evidence verifier for Bordeaux C-UAS golden demo.

Subscribes to NATS via nats CLI and validates delegation payload fields.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

NATS_URL = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
TIMEOUT_SEC = float(os.environ.get("VERIFY_TIMEOUT", "120"))

SUBJECTS = [
    "furia.s1.mission-delegation",
]


def main() -> int:
    sub_cmd = ["nats", "sub", "-s", NATS_URL, "--count", "1"] + SUBJECTS

    print(f"verify_origin.py: monitoring {len(SUBJECTS)} subjects on {NATS_URL}", flush=True)

    proc = subprocess.Popen(
        sub_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    delegation_seen = False
    delegation_valid = False
    passed = True
    errors: list[str] = []
    start = time.monotonic()

    try:
        for line in proc.stdout or []:
            if time.monotonic() - start > TIMEOUT_SEC:
                break
            if line.startswith("[#"):
                if 'Received on "' in line:
                    subj = line.split('Received on "')[1].split('"')[0]
                    if subj == "furia.s1.mission-delegation":
                        delegation_seen = True
                        print(f"  ✓ MISSION DELEGATION observed", flush=True)
            elif line.startswith("{"):
                try:
                    payload = json.loads(line)
                    if payload.get("correlationId") and payload.get("missionId"):
                        if payload["missionId"] == "perimeter_defense_fob":
                            delegation_valid = True
                            print(f"  ✓ Delegation payload: mission={payload['missionId']}, "
                                  f"correlation={payload['correlationId']}", flush=True)
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        print(f"verify_origin.py: error: {e}", flush=True)
    finally:
        proc.terminate()
        proc.wait()

    if not delegation_seen:
        errors.append("FAIL: no mission delegation observed")
        passed = False
    if not delegation_valid:
        errors.append("FAIL: delegation payload missing required fields")
        passed = False

    print("", flush=True)
    if passed:
        print("=== verify_origin.py: PASS ===", flush=True)
        return 0
    else:
        for err in errors:
            print(err, flush=True)
        print("=== verify_origin.py: FAIL ===", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())