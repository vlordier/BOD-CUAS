import json
import unittest
from pathlib import Path


PROFILE = Path(__file__).with_name("lfbd-operator-profile.json")


class AirportProfileContractTests(unittest.TestCase):
    def test_profile_is_versioned_and_complete(self) -> None:
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        self.assertEqual(profile["schema"], "bod-cuas.airport-operational-profile")
        self.assertTrue(profile["version"])
        self.assertEqual(profile["icao"], "LFBD")
        self.assertEqual(set(profile["bounds"]), {"minLat", "maxLat", "minLon", "maxLon"})
        self.assertGreater(len(profile["sensorSites"]), 0)
        self.assertGreater(len(profile["noFlyZones"]), 0)
        self.assertGreater(len(profile["replaySymbols"]), 0)
        self.assertIn("scenario", profile)
        self.assertIn("world3d", profile["assets"])

    def test_profile_keeps_runtime_paths_relative_to_the_host(self) -> None:
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        self.assertTrue(profile["assets"]["mapBackground"].startswith("/"))
        for key in ("assetBaseUrl", "groundImageUrl", "terrainGridUrl"):
            self.assertTrue(profile["assets"]["world3d"][key].startswith("/"))


if __name__ == "__main__":
    unittest.main()
