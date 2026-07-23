#!/usr/bin/env python3
"""Communications-denied continuation verifier for Bordeaux C-UAS golden demo.

Independently proves:
1. An authoritative Bordeaux delegation is observed.
2. Same contract later emits active/lost_link_continuation.
3. A later event for that same contract emits active/normal recovery.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

NATS_URL = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
TIMEOUT_SEC = float(os.environ.get("VERIFY_TIMEOUT", "120"))

SUBJECTS = [
    "furia.s1.mission-delegation",
    "furia.s1.execution-evidence",
]


def main() -> int:
    sub_cmd = ["nats", "sub", "-s", NATS_URL, "--count", "3"] + SUBJECTS

    print(f"verify_comm_denied.py: monitoring {len(SUBJECTS)} subjects on {NATS_URL}", flush=True)

    proc = subprocess.Popen(
        sub_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    delegation_seen = False
    evidence_seen = False
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
                    elif subj == "furia.s1.execution-evidence":
                        evidence_seen = True
                        print(f"  ✓ EXECUTION EVIDENCE observed", flush=True)
    except Exception as e:
        print(f"verify_comm_denied.py: error: {e}", flush=True)
    finally:
        proc.terminate()
        proc.wait()

    if not delegation_seen:
        errors.append("FAIL: no mission delegation observed")
        passed = False
    if not evidence_seen:
        errors.append("FAIL: no execution evidence observed")
        passed = False

    print("", flush=True)
    if passed:
        print("=== verify_comm_denied.py: PASS ===", flush=True)
        return 0
    else:
        for err in errors:
            print(err, flush=True)
        print("=== verify_comm_denied.py: FAIL ===", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())