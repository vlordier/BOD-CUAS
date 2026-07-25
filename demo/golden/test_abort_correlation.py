#!/usr/bin/env python3
"""Unit tests for the Core abort → S1 safe-hold correlation checks."""
from __future__ import annotations

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from verify import abort_matches_contract, delegation_contract, safe_hold_matches_contract


DELEGATION = {
    "mission_id": "perimeter_defense_fob",
    "correlation_id": "contract-4660",
    "cuas_constraints": {"target": {"track_id": "4660"}},
}
ABORT = {
    "action": "abort",
    "source": "core-safety-policy",
    "policy_id": "BOD-RWY-FRATRICIDE-003",
    "mission_id": "perimeter_defense_fob",
    "track_id": "4660",
}
SAFE_HOLD = {
    "contract_id": "contract-4660",
    "state": "aborted",
    "degraded_mode": "safety_hold",
    "rejection_reason": "core_safety_abort",
    "active_constraint_ids": ["BOD-RWY-FRATRICIDE-003"],
}


class AbortCorrelationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = delegation_contract(DELEGATION)
        assert self.contract is not None

    def test_extracts_delegation_contract(self) -> None:
        self.assertEqual(self.contract["correlation_id"], "contract-4660")
        self.assertEqual(self.contract["track_id"], "4660")

    def test_rejects_delegation_without_target_track(self) -> None:
        self.assertIsNone(delegation_contract({"mission_id": "m", "correlation_id": "c"}))

    def test_accepts_core_abort_for_delegated_mission_and_track(self) -> None:
        self.assertTrue(abort_matches_contract(ABORT, self.contract))

    def test_rejects_abort_for_other_track(self) -> None:
        command = {**ABORT, "track_id": "other"}
        self.assertFalse(abort_matches_contract(command, self.contract))

    def test_accepts_contract_correlated_safe_hold(self) -> None:
        self.assertTrue(safe_hold_matches_contract(SAFE_HOLD, self.contract))

    def test_rejects_safe_hold_without_core_abort_reason(self) -> None:
        evidence = {**SAFE_HOLD, "rejection_reason": "contract_expired"}
        self.assertFalse(safe_hold_matches_contract(evidence, self.contract))


if __name__ == "__main__":
    unittest.main()
