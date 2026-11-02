#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from loader import ScenarioError, load_all, load_scenario, scenario_digest, validate_scenario


ROOT = Path(__file__).parent


class ResilienceScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scenarios = load_all(ROOT / "scenarios")

    def test_all_five_fixtures_load_in_stable_order(self) -> None:
        self.assertEqual(
            [scenario["id"] for scenario in self.scenarios],
            [
                "authority-expiry",
                "multi-threat-saturation",
                "runway-state-change",
                "sensor-conflict",
                "stale-track",
            ],
        )

    def test_every_fixture_has_complete_deterministic_contract(self) -> None:
        for scenario in self.scenarios:
            with self.subTest(scenario=scenario["id"]):
                self.assertEqual(scenario["version"], "1.0.0")
                self.assertIsInstance(scenario["seed"], int)
                self.assertGreaterEqual(scenario["seed"], 0)
                self.assertTrue(scenario["actors"])
                self.assertTrue(scenario["sensors"])
                self.assertIn("authority", scenario)
                self.assertTrue(scenario["expected_outcome"]["assertions"])
                self.assertEqual(scenario_digest(scenario), scenario_digest(load_scenario(ROOT / "scenarios" / f"{scenario['id']}.json")))

    def test_scenario_specific_faults_and_outcomes_are_present(self) -> None:
        by_id = {scenario["id"]: scenario for scenario in self.scenarios}
        self.assertIn("disagreement", {fault["type"] for fault in by_id["sensor-conflict"]["faults"]})
        self.assertIn("stale_data", {fault["type"] for fault in by_id["stale-track"]["faults"]})
        self.assertIn("authority_expiry", {fault["type"] for fault in by_id["authority-expiry"]["faults"]})
        self.assertGreaterEqual(len(by_id["multi-threat-saturation"]["actors"]), 6)
        self.assertIn("runway_state_change", {fault["type"] for fault in by_id["runway-state-change"]["faults"]})

    def test_digest_changes_when_scenario_changes(self) -> None:
        scenario = copy.deepcopy(self.scenarios[0])
        original = scenario_digest(scenario)
        scenario["seed"] += 1
        self.assertNotEqual(original, scenario_digest(scenario))

    def test_invalid_reference_is_rejected(self) -> None:
        scenario = copy.deepcopy(self.scenarios[0])
        scenario["sensors"][0]["observes"] = ["missing-actor"]
        with self.assertRaisesRegex(ScenarioError, "unknown actor"):
            validate_scenario(scenario)

    def test_invalid_authority_window_is_rejected(self) -> None:
        scenario = copy.deepcopy(self.scenarios[0])
        scenario["authority"]["valid_until_ms"] = scenario["authority"]["valid_from_ms"]
        with self.assertRaisesRegex(ScenarioError, "valid_until_ms"):
            validate_scenario(scenario)

    def test_fixture_files_are_json_objects(self) -> None:
        for path in sorted((ROOT / "scenarios").glob("*.json")):
            with self.subTest(path=path.name):
                self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)


if __name__ == "__main__":
    unittest.main()
