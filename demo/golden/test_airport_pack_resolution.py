import json
import tempfile
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.airport_pack import resolve_airport_pack


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "demo/golden/airport-packs/lfbd/manifest.json"


class AirportPackResolutionTests(unittest.TestCase):
    def test_resolves_all_components_without_airport_specific_code(self):
        resolved = resolve_airport_pack(MANIFEST)
        self.assertEqual(resolved["schema"], "bod-cuas.resolved-airport-pack")
        self.assertEqual(
            set(resolved["components"]),
            {"identity", "geodata", "sensors", "sectors", "scenarios"},
        )
        self.assertEqual(resolved["components"]["identity"]["data"]["icao"], "LFBD")
        self.assertEqual(len(resolved["components"]["sensors"]["data"]["sensors"]), 7)
        self.assertEqual(len(resolved["components"]["scenarios"]["data"]["scenarios"]), 4)

    def test_output_is_json_serializable_and_paths_are_repository_relative(self):
        resolved = resolve_airport_pack(MANIFEST)
        encoded = json.dumps(resolved, ensure_ascii=False)
        self.assertIn("airport-packs/lfbd/manifest.json", encoded)
        self.assertNotIn(str(ROOT), encoded)

    def test_reference_escape_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            path = Path(temp) / "manifest.json"
            path.write_text(
                json.dumps({
                    "schema": "bod-cuas.airport-pack",
                    "version": "1.0.0",
                    "id": "test-pack",
                    "display_name": "Test",
                    "authority_boundary": "training_only",
                    "components": {key: "../../../../etc/passwd" for key in ("identity", "geodata", "sensors", "sectors", "scenarios")},
                }),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                resolve_airport_pack(path)


if __name__ == "__main__":
    unittest.main()
