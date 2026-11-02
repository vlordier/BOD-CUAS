import json
import unittest
from pathlib import Path

SCENARIO = json.loads(Path(__file__).with_name("hybrid-demo-scenario.json").read_text())


class HybridScenarioTest(unittest.TestCase):
    def test_scenario_is_training_only_and_has_a_complete_story(self):
        self.assertEqual(SCENARIO["mode"], "training_only")
        self.assertEqual([stage["id"] for stage in SCENARIO["stages"]][-2:], ["hold", "review"])
        self.assertGreaterEqual(len(SCENARIO["stages"]), 8)

    def test_public_context_feeds_cannot_create_authority(self):
        for feed in SCENARIO["context_feeds"]:
            self.assertEqual(feed["authority"], "context_only")
        self.assertIn("authority", SCENARIO["safety_boundary"])
        self.assertIn("simulated", SCENARIO["safety_boundary"])

    def test_counterfactuals_are_analysis_only(self):
        ids = {item["id"] for item in SCENARIO["counterfactuals"]}
        self.assertEqual(len(ids), len(SCENARIO["counterfactuals"]))
        self.assertTrue(all(item["result"] for item in SCENARIO["counterfactuals"]))


if __name__ == "__main__":
    unittest.main()
