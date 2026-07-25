#!/usr/bin/env python3
"""Golden demo acceptance verifier — monitors canonical Core-admitted event stream
and validates JSON payload fields for causal ordering.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from urllib.parse import urlparse

NATS_URL = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
TIMEOUT_SEC = float(os.environ.get("VERIFY_TIMEOUT", "120"))

SUBJECTS = [
    "scenario.status",
    "furia.s1.mission-delegation",
    "swarm.command.abort",
    "furia.s1.execution-evidence",
]


def delegation_contract(payload: dict) -> dict | None:
    """Extract the only safe join key available for Core abort commands.

    Core's canonical abort does not carry an S1 correlation ID. The verifier
    therefore joins it to the delegation by mission + delegated target track,
    then requires S1's evidence to carry that delegation correlation ID.
    """
    constraints = payload.get("cuas_constraints") or {}
    target = constraints.get("target") or {}
    mission_id = payload.get("mission_id")
    correlation_id = payload.get("correlation_id")
    track_id = target.get("track_id")
    if not all(isinstance(value, str) and value.strip() for value in (mission_id, correlation_id, track_id)):
        return None
    return {
        "mission_id": mission_id,
        "correlation_id": correlation_id,
        "track_id": track_id,
    }


def abort_matches_contract(payload: dict, contract: dict) -> bool:
    return (
        payload.get("action") == "abort"
        and payload.get("source") == "core-safety-policy"
        and payload.get("policy_id") == "BOD-RWY-FRATRICIDE-003"
        and payload.get("mission_id") == contract["mission_id"]
        and payload.get("track_id") == contract["track_id"]
    )


def safe_hold_matches_contract(payload: dict, contract: dict) -> bool:
    return (
        payload.get("contract_id") == contract["correlation_id"]
        and payload.get("state") == "aborted"
        and payload.get("degraded_mode") == "safety_hold"
        and payload.get("rejection_reason") == "core_safety_abort"
        and "BOD-RWY-FRATRICIDE-003" in payload.get("active_constraint_ids", [])
    )


def main() -> int:
    # Use timeout as outer safety net, --count as inner limiter
    sub_cmd = ["timeout", str(int(TIMEOUT_SEC)), "nats", "sub", "-s", NATS_URL, "--count", "7"] + SUBJECTS

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
    delegation_seen = False
    abort_command_seen = False
    scenario_status_seen = False

    # Payload validation counters
    delegation_valid = False
    abort_valid = False
    safe_hold_valid = False
    contract: dict | None = None
    current_subject: str | None = None

    try:
        for line in proc.stdout or []:
            if time.monotonic() - start > TIMEOUT_SEC:
                break
            if line.startswith("[#"):
                if 'Received on "' in line:
                    subj = line.split('Received on "')[1].split('"')[0]
                    current_subject = subj
                    now = time.monotonic()
                    if subj not in first_seen:
                        first_seen[subj] = now

                    if subj == "scenario.status":
                        scenario_status_seen = True
                        print(f"  ✓ SCENARIO STATUS observed", flush=True)
                    elif subj == "furia.s1.mission-delegation":
                        delegation_seen = True
                        print(f"  ✓ MISSION DELEGATION observed", flush=True)
                    elif subj == "swarm.command.abort":
                        abort_command_seen = True
                        print(f"  ✓ ABORT COMMAND observed", flush=True)
                    elif subj == "furia.s1.execution-evidence":
                        print(f"  ✓ EXECUTION EVIDENCE observed", flush=True)
            elif line.startswith("{"):
                # JSON payload line — validate content
                try:
                    payload = json.loads(line)
                    if current_subject == "furia.s1.mission-delegation":
                        candidate = delegation_contract(payload)
                        if candidate and candidate["mission_id"] == "perimeter_defense_fob":
                            contract = candidate
                            delegation_valid = True
                            print(f"  ✓ Delegation payload: mission={payload['mission_id']}, "
                                  f"correlation={payload['correlation_id']}", flush=True)
                    elif current_subject == "swarm.command.abort":
                        if contract and abort_matches_contract(payload, contract):
                            abort_valid = True
                            print(f"  ✓ Abort correlated: mission={payload['mission_id']}, "
                                  f"track={payload['track_id']}, contract={contract['correlation_id']}", flush=True)
                    elif current_subject == "furia.s1.execution-evidence":
                        if contract and abort_valid and safe_hold_matches_contract(payload, contract):
                            safe_hold_valid = True
                            print(f"  ✓ S1 SAFE HOLD correlated: contract={contract['correlation_id']}", flush=True)
                except json.JSONDecodeError:
                    pass
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

    if scenario_status_seen:
        print("  ✓ Causal: scenario status observed", flush=True)
    else:
        errors.append("FAIL: no scenario status observed")
        passed = False

    # Payload validation
    if delegation_valid:
        print("  ✓ Payload: delegation fields valid", flush=True)
    else:
        errors.append("FAIL: delegation payload missing required fields")
        passed = False

    if abort_valid:
        print("  ✓ Payload: Core abort matches delegated mission and target", flush=True)
    else:
        errors.append("FAIL: abort does not match delegated mission and target")
        passed = False

    if safe_hold_valid:
        print("  ✓ Evidence: S1 safe hold acknowledges the Core abort contract", flush=True)
    else:
        errors.append("FAIL: no contract-correlated S1 safe-hold evidence after Core abort")
        passed = False

    # Ordering: delegation should come before abort
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
