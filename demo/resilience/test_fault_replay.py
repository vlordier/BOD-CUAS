import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from replay_faults import load_scenario, replay  # noqa: E402


class FaultReplayTests(unittest.TestCase):
    def scenario(self):
        return {
            "scenario_id": "fault-pack",
            "seed": 19,
            "events": [
                {"id": "radar", "at_ms": 100, "subject": "surveillance.observation", "data": {"track_id": "4660"}},
                {"id": "rf", "at_ms": 200, "subject": "surveillance.observation", "data": {"track_id": "4660"}},
                {"id": "authority", "at_ms": 300, "subject": "furia.s1.mission-delegation", "data": {"track_id": "4660", "authority": {"source": "fixture-only"}}},
            ],
            "faults": {
                "latency_ms": 50,
                "clock_skew_ms": 10,
                "stale_after_ms": 500,
                "duplicate": {"ids": ["radar"], "count": 1},
                "reorder_window": 2,
                "identity_mismatch": {"ids": ["rf"], "observed_track_id": "9999"},
            },
        }

    def test_all_faults_are_explicit_and_authority_is_read_only(self):
        records, summary = replay(self.scenario())
        self.assertEqual(summary["input_events"], 3)
        self.assertEqual(summary["emitted_events"], 4)
        self.assertEqual(summary["duplicate_events"], 1)
        self.assertEqual(summary["authority_records_created"], 0)
        rf = next(record for record in records if record["event_id"] == "rf")
        self.assertEqual(rf["data"]["source_track_id"], "4660")
        self.assertEqual(rf["data"]["track_id"], "9999")
        self.assertTrue(rf["data"]["stale"])
        self.assertEqual(rf["observed_at_ms"], 260)
        authority = next(record for record in records if record["event_id"] == "authority")
        self.assertEqual(authority["authority_observed"], {"authority": {"source": "fixture-only"}})

    def test_loss_is_deterministic(self):
        scenario = self.scenario()
        scenario["faults"] = {"loss": {"ids": ["rf"]}}
        first = replay(scenario)
        second = replay(scenario)
        self.assertEqual(first, second)
        self.assertEqual(first[1]["dropped_events"], 1)
        self.assertNotIn("rf", {record["event_id"] for record in first[0]})

    def test_probability_loss_is_seeded_not_all_or_none(self):
        scenario = {
            "scenario_id": "probability",
            "seed": 3,
            "events": [{"id": str(index), "at_ms": index} for index in range(20)],
            "faults": {"loss": 0.5},
        }
        records, summary = replay(scenario)
        self.assertGreater(summary["dropped_events"], 0)
        self.assertGreater(summary["emitted_events"], 0)
        self.assertEqual(summary["input_events"], 20)
        self.assertEqual(len(records) + summary["dropped_events"], 20)

    def test_no_authority_is_invented(self):
        scenario = self.scenario()
        scenario["events"] = [scenario["events"][0]]
        records, summary = replay(scenario)
        self.assertEqual(records[0]["authority_observed"], {})
        self.assertEqual(summary["authority_records_observed"], 0)
        self.assertEqual(summary["authority_records_created"], 0)
        self.assertNotIn("delegation", json.dumps(records))

    def test_cli_emits_jsonl_and_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "scenario.json"
            output = root / "events.jsonl"
            summary = root / "summary.json"
            fixture.write_text(json.dumps(self.scenario()), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("replay_faults.py")), "--scenario", str(fixture), "--output", str(output), "--summary-output", str(summary)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(output.read_text(encoding="utf-8").splitlines()), 4)
            self.assertEqual(json.loads(summary.read_text(encoding="utf-8"))["emitted_events"], 4)
            self.assertIn("emitted=4", result.stderr)

    def test_default_scenario_is_available(self):
        scenario = load_scenario(None, Path(__file__).parent)
        records, summary = replay(scenario)
        self.assertEqual(scenario["source_dsl"], "furia.cuas.resilience-scenario")
        self.assertGreater(summary["emitted_events"], 1)
        self.assertEqual(records[0]["subject"], "surveillance.observation")

    def test_repository_dsl_fixtures_expand_without_authority_actions(self):
        fixture_dir = Path(__file__).parent / "scenarios"
        fixtures = sorted(fixture_dir.glob("*.json"))
        self.assertEqual(len(fixtures), 5)
        for fixture in fixtures:
            with self.subTest(fixture=fixture.name):
                scenario = load_scenario(fixture)
                records, summary = replay(scenario)
                self.assertTrue(records)
                self.assertEqual(summary["authority_records_created"], 0)
                self.assertEqual(summary["source_dsl"], "furia.cuas.resilience-scenario")


if __name__ == "__main__":
    unittest.main()
