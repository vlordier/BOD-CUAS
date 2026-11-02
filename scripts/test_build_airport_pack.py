import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_airport_pack import build
from airport_pack import resolve_airport_pack
from validate_airport_pack import validate


class AirportPackBuilderTest(unittest.TestCase):
    def test_builds_unknown_icao_from_minimal_source(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
            root = Path(directory)
            source = root / "source.json"
            output = root / "pack"
            source.write_text(json.dumps({
                "icao": "LFXX", "iata": "XXX", "name": "Test airport", "country": "FR",
                "reference_point": {"latitude": 45.0, "longitude": 1.0},
                "bounds": {"min_latitude": 44.9, "max_latitude": 45.1, "min_longitude": 0.9, "max_longitude": 1.1}
            }), encoding="utf-8")
            manifest = build(source, output)
            self.assertEqual(validate(manifest)[0], "lfxx-airport-pack: LFXX")
            self.assertTrue((output / "profile.json").is_file())
            self.assertTrue((output / "catalogue.json").is_file())
            self.assertEqual(json.loads((output / "validation-report.json").read_text())["status"], "validated")

    def test_rejects_invalid_icao(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            source.write_text(json.dumps({"icao": "bad"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "four-letter"):
                build(source, root / "pack")

    def test_second_configured_airport_pack_validates_and_resolves_without_lfbd_data(self):
        """Prove the generic path with a temporary, explicitly synthetic pack."""
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
            root = Path(directory)
            source = root / "source.json"
            output = root / "pack"
            source.write_text(json.dumps({
                "icao": "LFYY", "iata": "YYY", "name": "Synthetic secondary airport", "country": "FR",
                "reference_point": {"latitude": 46.0, "longitude": 2.0},
                "bounds": {"min_latitude": 45.9, "max_latitude": 46.1, "min_longitude": 1.9, "max_longitude": 2.1},
                "data_status": "synthetic_demo_context"
            }), encoding="utf-8")

            manifest = build(source, output)
            self.assertEqual(validate(manifest)[0], "lfyy-airport-pack: LFYY")
            resolved = resolve_airport_pack(manifest)
            self.assertEqual(resolved["components"]["identity"]["data"]["icao"], "LFYY")
            self.assertEqual(resolved["manifest"]["authority_boundary"], "training_only")
            self.assertNotIn("LFBD", json.dumps(resolved))


if __name__ == "__main__":
    unittest.main()
