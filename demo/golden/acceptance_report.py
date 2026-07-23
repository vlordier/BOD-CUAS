#!/usr/bin/env python3
"""Generate machine-readable acceptance report for the Bordeaux C-UAS golden demo.

Reads verifier logs and produces a JSON report with 1:1 check-to-log mapping.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

LOG_DIR = os.environ.get(
    "GOLDEN_LOG_DIR",
    os.path.join(os.environ.get("TMPDIR", tempfile.gettempdir()), "furia-bod-golden"),
)

# 1:1 mapping — each verifier log maps to exactly one check
CHECKS = {
    "causal_ordering": "verify.log",
    "delegation_observed": "verify-origin.log",
    "lost_link_continuation": "verify-comm-denied.log",
}


def main() -> int:
    report: dict[str, bool | str | dict] = {
        "result": "PASS",
        "scenario": "bod-cuas-golden",
        "checks": {},
    }

    all_pass = True
    for check_name, log_file in CHECKS.items():
        log_path = os.path.join(LOG_DIR, log_file)
        if not os.path.isfile(log_path):
            report["checks"][check_name] = False
            all_pass = False
            continue

        with open(log_path) as f:
            content = f.read()

        passed = "PASS" in content
        report["checks"][check_name] = passed
        if not passed:
            all_pass = False

    report["result"] = "PASS" if all_pass else "FAIL"
    report["log_dir"] = LOG_DIR

    print(json.dumps(report, indent=2))
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())