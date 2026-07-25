#!/usr/bin/env python3
"""Contract checks for the additive C2-only operational context fixture."""
from __future__ import annotations

import json
from pathlib import Path
import unittest


FIXTURE = Path(__file__).with_name("operational-context.json")


class OperationalContextFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = json.loads(FIXTURE.read_text())
        self.example = self.fixture["example"]

    def test_fixture_is_versioned_and_explicitly_non_authoritative(self) -> None:
        self.assertEqual(self.fixture["schema"], "furia.cuas.operational-context")
        self.assertEqual(self.fixture["version"], "1.0.0")
        self.assertEqual(self.fixture["subject"], "cuas.operational.context")
        self.assertIn("not an authoritative command", self.fixture["purpose"])

    def test_abort_example_is_actionable_without_claiming_execution_confirmation(self) -> None:
        self.assertEqual(self.example["phase"], "safety_abort_pending_execution_evidence")
        self.assertEqual(self.example["safety"]["state"], "abort_issued")
        self.assertEqual(self.example["authority"]["execution_acknowledgement"], "pending_safe_hold_evidence")
        self.assertEqual(self.example["safety"]["civil_flight"]["callsign"], "AFR762")

    def test_predicted_entry_is_runway_scoped_and_bounded(self) -> None:
        entry = self.example["threat"]["predicted_entry"]
        self.assertEqual(entry["runway_or_sector"], "RWY23")
        self.assertGreater(entry["time_to_entry_ms"], 0)
        self.assertGreater(entry["horizontal_uncertainty_mm"], 0)


if __name__ == "__main__":
    unittest.main()
