import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/geodata"))
from import_airport_open_data import build_manifest


class GenericGeodataImportTest(unittest.TestCase):
    def test_manifest_is_airport_agnostic_and_context_only(self):
        terrain = {"bbox": {"south": 1, "west": 2, "north": 3, "east": 4}, "source": "DEM", "license": "open"}
        buildings = {"metadata": {"source": "OSM", "license": "ODbL"}}
        manifest = build_manifest("LFXX", terrain, buildings)
        self.assertEqual(manifest["airport_icao"], "LFXX")
        self.assertEqual(manifest["authority"], "context_only")
        self.assertEqual(manifest["layers"]["buildings"], "buildings.geojson")
        self.assertIn("AIP", json.dumps(manifest))
        self.assertEqual(manifest["provenance"]["review_status"], "pending_context_review")


if __name__ == "__main__":
    unittest.main()
