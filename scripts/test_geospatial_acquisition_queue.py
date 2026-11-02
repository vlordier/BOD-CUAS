import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_geospatial_acquisition_queue import build_queue


class GeospatialAcquisitionQueueTest(unittest.TestCase):
    def test_missing_geometry_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = build_queue({"source_id": "test", "status": "historical", "airports": [{"icao": "LFXX", "name": "Test"}]}, root)
        self.assertEqual(result["summary"]["acquisition_required"], 1)
        self.assertEqual(result["airports"][0]["status"], "source_acquisition_required")
        self.assertIsNone(result["airports"][0]["pack_path"])
        self.assertEqual(result["airports"][0]["operational_claim"], "none")

    def test_existing_pack_is_review_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pack = root / "data/geospatial/lfxx"
            pack.mkdir(parents=True)
            (pack / "manifest.json").write_text("{}", encoding="utf-8")
            result = build_queue({"source_id": "test", "status": "partial", "airports": [{"icao": "LFXX", "name": "Test"}]}, root)
        self.assertEqual(result["summary"]["packs_present"], 1)
        self.assertEqual(result["airports"][0]["status"], "context_pack_present_needs_review")

    def test_current_reference_produces_review_only_bbox(self):
        with tempfile.TemporaryDirectory() as directory:
            result = build_queue(
                {"source_id": "test", "status": "partial", "airports": [{"icao": "LFXX", "name": "Test"}]},
                Path(directory),
                {"airports": [{"icao": "LFXX", "reference_point": {"latitude": 45.0, "longitude": 1.0}, "source_status": "matched_current_reference"}]},
                1000,
            )
        item = result["airports"][0]
        self.assertEqual(item["status"], "reference_ready_bbox_review")
        self.assertEqual(item["candidate_bbox_status"], "derived_for_review_only")
        self.assertAlmostEqual(item["candidate_bbox_wgs84"]["south"], 44.991016, places=5)


if __name__ == "__main__":
    unittest.main()
