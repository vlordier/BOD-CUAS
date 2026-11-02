import copy
import importlib.util
import json
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("coverage.py")
SPEC = importlib.util.spec_from_file_location("bod_cuas_coverage", MODULE_PATH)
assert SPEC and SPEC.loader
coverage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(coverage)


class CoverageManifestTests(unittest.TestCase):
    def test_manifest_is_valid(self):
        self.assertEqual(coverage.validate_manifest(), [])

    def test_report_is_machine_readable_and_complete(self):
        report = coverage.build_report()
        json.dumps(report)
        self.assertTrue(report["manifest_valid"])
        self.assertEqual(report["summary"]["verified"], 2)
        self.assertEqual(report["summary"]["partial"], 5)
        self.assertEqual(report["summary"]["not_implemented"], 0)
        self.assertIn("safe_hold_confirmed", report["summary"]["verified_safety_states"])
        self.assertIn("authorization_pending", report["summary"]["verified_safety_states"])

    def test_every_scenario_has_inputs_and_states(self):
        for scenario in coverage.SCENARIOS:
            self.assertTrue(scenario["inputs"], scenario["id"])
            self.assertTrue(scenario["safety_states"], scenario["id"])

    def test_missing_expected_outcome_fails_closed(self):
        scenarios = copy.deepcopy(coverage.SCENARIOS)
        scenarios[0]["expected_outcomes"] = []
        errors = coverage.validate_manifest(tuple(scenarios))
        self.assertTrue(any("expected_outcomes is required" in error for error in errors))

    def test_missing_authority_boundary_fails_closed(self):
        scenarios = copy.deepcopy(coverage.SCENARIOS)
        scenarios[0]["authority_boundary"] = None
        errors = coverage.validate_manifest(tuple(scenarios))
        self.assertTrue(any("authority_boundary.owner is required" in error for error in errors))

    def test_unknown_state_fails_closed(self):
        scenarios = copy.deepcopy(coverage.SCENARIOS)
        scenarios[0]["safety_states"].append("imaginary_state")
        errors = coverage.validate_manifest(tuple(scenarios))
        self.assertTrue(any("unknown safety states" in error for error in errors))

    def test_markdown_report_names_unimplemented_targets(self):
        rendered = coverage.markdown_report(coverage.build_report())
        self.assertIn("sensor-conflict", rendered)
        self.assertIn("not_implemented", rendered)
        self.assertIn("authority boundary", rendered)


if __name__ == "__main__":
    unittest.main()
