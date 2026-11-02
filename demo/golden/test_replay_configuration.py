#!/usr/bin/env python3
"""Contract tests for deployment-neutral replay metadata."""

from __future__ import annotations

import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parent


class ReplayConfigurationTests(unittest.TestCase):
    def run_probe(self, **overrides: str) -> str:
        env = os.environ.copy()
        env.update(overrides)
        probe = (
            "import replay; "
            "print(replay.airport_context(replay.DEFAULT_AFFECTED_SECTOR)); "
            "print(replay.SCENARIO_ID); "
            "print(replay.PROTECTED_VOLUME_ID)"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout

    def test_default_profile_remains_bordeaux_compatibility_data(self) -> None:
        output = self.run_probe()
        self.assertIn("'icao': 'LFBD'", output)
        self.assertIn("'active_runway': '05/23'", output)

    def test_operator_context_can_be_retargeted_without_editing_replay(self) -> None:
        output = self.run_probe(
            DEMO_AIRPORT_ICAO="LFPG",
            DEMO_AIRPORT_NAME="Paris-CDG",
            DEMO_ACTIVE_RUNWAY="09/27",
            DEMO_AFFECTED_SECTOR="approche est",
            DEMO_PROTECTED_VOLUME_ID="approach-09",
            DEMO_SCENARIO_ID="paris-cuas-training",
        )
        self.assertIn("'icao': 'LFPG'", output)
        self.assertIn("'name': 'Paris-CDG'", output)
        self.assertIn("'active_runway': '09/27'", output)
        self.assertIn("'affected_sector': 'approche est'", output)
        self.assertIn("paris-cuas-training", output)
        self.assertIn("approach-09", output)

    def test_versioned_profile_can_supply_a_new_airport_without_code_changes(self) -> None:
        profile = {
            "schema": "bod-cuas.replay-profile",
            "version": "2.0.0",
            "scenario_id": "lyon-cuas-training",
            "airport": {
                "icao": "LFLL",
                "name": "Lyon-Saint-Exupéry",
                "active_runway": "17/35",
                "affected_sector": "approche sud",
            },
            "protected_volume_id": "approach-17",
            "civil_flight_id": "AFR123",
            "safety_policy_id": "LYS-RWY-SAFETY-001",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile["airport_pack_manifest"] = "manifest.json"
            (root / "manifest.json").write_text(json.dumps({
                "schema": "bod-cuas.airport-pack",
                "components": {"identity": "identity.json"},
            }), encoding="utf-8")
            (root / "identity.json").write_text(json.dumps({
                "schema": "bod-cuas.airport-pack.identity",
                "icao": "LFLL",
            }), encoding="utf-8")
            profile_path = root / "replay-profile.json"
            profile_path.write_text(json.dumps(profile), encoding="utf-8")
            output = self.run_probe(DEMO_REPLAY_PROFILE=str(profile_path))
        self.assertIn("'icao': 'LFLL'", output)
        self.assertIn("'name': 'Lyon-Saint-Exupéry'", output)
        self.assertIn("lyon-cuas-training", output)
        self.assertIn("approach-17", output)


if __name__ == "__main__":
    unittest.main()
