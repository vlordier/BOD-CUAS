#!/usr/bin/env python3
"""Policy-level assertions for the deterministic Bordeaux C-UAS replay."""
from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


REPLAY_PATH = Path(__file__).with_name("replay.py")
REPLAY_SOURCE = REPLAY_PATH.read_text(encoding="utf-8")
REPLAY_TREE = ast.parse(REPLAY_SOURCE)
CONTEXT_FIXTURE = json.loads(
    Path(__file__).with_name("operational-context.json").read_text(encoding="utf-8")
)


class GoldenReplayPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.subjects = {
            node.value
            for node in ast.walk(REPLAY_TREE)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and ("." in node.value or node.value.startswith("furia."))
        }

    def test_replay_is_stimulus_only_and_uses_versioned_subjects(self) -> None:
        self.assertIn("surveillance.observation", self.subjects)
        self.assertIn("operator.action.authorized", self.subjects)
        self.assertIn("safety.civilian_aircraft_conflict", self.subjects)
        self.assertNotIn("swarm.intent.submit", self.subjects)
        self.assertIn("OPERATIONAL_CONTEXT_SUBJECT", REPLAY_SOURCE)

    def test_sensor_degradation_does_not_clear_threat(self) -> None:
        self.assertIn('"connection_status": "degraded"', REPLAY_SOURCE)
        self.assertNotIn('"phase": "assessment"', REPLAY_SOURCE)
        self.assertIn('"connection_status": "degraded"', REPLAY_SOURCE)
        self.assertIn('"classification": "non_cooperative_uas"', REPLAY_SOURCE)

    def test_unknown_cooperative_is_not_treated_as_hostile(self) -> None:
        self.assertIn('"event": "unknown_cooperative_uas"', REPLAY_SOURCE)
        self.assertIn('"authorization": "unknown"', REPLAY_SOURCE)
        self.assertIn('"severity": "attention"', REPLAY_SOURCE)

    def test_operator_authorization_has_named_decision_authority(self) -> None:
        self.assertIn('"operator": "demo-operator"', REPLAY_SOURCE)
        self.assertIn('"authorization_id": "bod-demo-auth-4660"', REPLAY_SOURCE)

    def test_control_path_uses_versioned_bounded_delegation(self) -> None:
        # Replay must not fabricate Core/S1 outputs. Those subjects are
        # asserted by the live verifiers and correlation tests instead.
        self.assertNotIn("furia.s1.mission-delegation", REPLAY_SOURCE)
        self.assertNotIn("swarm.command.abort", REPLAY_SOURCE)
        self.assertIn('"posture": "authorization_pending"', REPLAY_SOURCE)
        self.assertIn('"valid_for_sec": 270', REPLAY_SOURCE)

    def test_operational_context_is_runway_scoped_and_explicitly_training(self) -> None:
        self.assertEqual(CONTEXT_FIXTURE["version"], "2.0.0")
        example = CONTEXT_FIXTURE["example"]
        self.assertEqual(example["airport"]["icao"], "LFBD")
        self.assertEqual(example["airport"]["mode"], "training_replay")
        self.assertEqual(example["threat"]["predicted_entry"]["runway_or_sector"], "RWY23")

    def test_civilian_conflict_is_explicitly_an_inhibition(self) -> None:
        self.assertIn("safety.civilian_aircraft_conflict", REPLAY_SOURCE)
        self.assertIn('"posture": "intercept_inhibited"', REPLAY_SOURCE)
        self.assertIn('"execution_acknowledgement": "pending_safe_hold_evidence"', REPLAY_SOURCE)


if __name__ == "__main__":
    unittest.main()
