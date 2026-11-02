import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_current_airport_reference import import_reference


class CurrentAirportReferenceTest(unittest.TestCase):
    def test_matches_coordinates_and_keeps_non_operational_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            airports = root / "airports.csv"
            runways = root / "runways.csv"
            with airports.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["icao_code", "ident", "iso_country", "latitude_deg", "longitude_deg", "elevation_ft"])
                writer.writeheader()
                writer.writerow({"icao_code": "LFXX", "ident": "LFXX", "iso_country": "FR", "latitude_deg": "45.0", "longitude_deg": "1.0", "elevation_ft": "100"})
            with runways.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["airport_ident", "closed", "length_ft", "width_ft", "surface", "le_ident", "he_ident"])
                writer.writeheader()
                writer.writerow({"airport_ident": "LFXX", "closed": "0", "length_ft": "1000", "width_ft": "30", "surface": "ASP", "le_ident": "09", "he_ident": "27"})
            result = import_reference({"airports": [{"icao": "LFXX", "name": "Test"}]}, airports, runways, "2026-01-01T00:00:00Z")
        self.assertEqual(result["summary"], {"inventory_total": 1, "matched": 1, "unmatched": 0})
        self.assertEqual(result["airports"][0]["reference_point"]["latitude"], 45.0)
        self.assertEqual(result["airports"][0]["operational_status"], "not_operational")
        self.assertEqual(result["airports"][0]["geometry_use"], "candidate_bbox_input_only")

    def test_alias_is_explicit_and_auditable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            airports = root / "airports.csv"
            runways = root / "runways.csv"
            fields = ["icao_code", "ident", "iso_country", "latitude_deg", "longitude_deg", "elevation_ft"]
            with airports.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerow({"icao_code": "NTAA", "ident": "NTAA", "iso_country": "PF", "latitude_deg": "-17.55", "longitude_deg": "-149.61", "elevation_ft": "5"})
            with runways.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["airport_ident", "closed", "length_ft", "width_ft", "surface", "le_ident", "he_ident"])
                writer.writeheader()
            result = import_reference({"airports": [{"icao": "NTTT", "name": "Tahiti"}]}, airports, runways, aliases={"NTTT": "NTAA"})
        item = result["airports"][0]
        self.assertTrue(item["reference_alias_used"])
        self.assertEqual(item["reference_icao"], "NTAA")


if __name__ == "__main__":
    unittest.main()
