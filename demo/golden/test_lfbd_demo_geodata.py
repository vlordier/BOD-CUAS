#!/usr/bin/env python3
"""Validation for the versioned, non-operational LFBD demo map model."""
from __future__ import annotations

import json
from pathlib import Path
import unittest


FIXTURE = Path(__file__).with_name("lfbd-demo-geodata.json")


def walk_positions(value: object):
    if isinstance(value, list) and len(value) == 2 and all(isinstance(v, (int, float)) for v in value):
        yield value
    elif isinstance(value, list):
        for child in value:
            yield from walk_positions(child)


class LfbdDemoGeodataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = json.loads(FIXTURE.read_text())
        self.features = self.model["features"]

    def test_model_is_versioned_and_explicitly_demo_only(self) -> None:
        self.assertEqual(self.model["schema"], "furia.cuas.demo-geodata")
        self.assertEqual(self.model["version"], "1.0.0")
        self.assertEqual(self.model["airport"]["icao"], "LFBD")
        self.assertIn("demo_only", self.model["provenance"]["status"])

    def test_all_feature_ids_and_geometries_are_valid(self) -> None:
        ids = [feature["id"] for feature in self.features]
        self.assertEqual(len(ids), len(set(ids)))
        for feature in self.features:
            geometry = feature["geometry"]
            self.assertIn(geometry["type"], {"Point", "LineString", "Polygon"})
            for longitude, latitude in walk_positions(geometry["coordinates"]):
                self.assertGreaterEqual(longitude, -180)
                self.assertLessEqual(longitude, 180)
                self.assertGreaterEqual(latitude, -90)
                self.assertLessEqual(latitude, 90)

    def test_required_operational_context_layers_are_present(self) -> None:
        kinds = {feature["kind"] for feature in self.features}
        self.assertTrue({"runway", "terminal_apron", "approach_corridor", "departure_corridor", "protected_volume", "rf_sensor_site"}.issubset(kinds))
        policy_ids = {feature.get("policy_fixture_id") for feature in self.features}
        self.assertTrue({"runway-05-23-core", "apron-critical"}.issubset(policy_ids))


if __name__ == "__main__":
    unittest.main()
