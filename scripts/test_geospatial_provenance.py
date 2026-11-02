import json
import shutil
import tempfile
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from validate_geospatial_provenance import validate_manifest, validate_registry
from audit_airport_geospatial_readiness import audit


ROOT = Path(__file__).resolve().parents[1]


class GeospatialProvenanceTest(unittest.TestCase):
    def test_lfbd_context_passes_quality_gates(self):
        self.assertIn("operational_status=context_only", validate_manifest(ROOT / "data/geospatial/lfbd/manifest.json"))

    def test_registry_is_explicitly_partial(self):
        self.assertIn("explicitly partial", validate_registry(ROOT / "data/geospatial/france-airports-registry.json")[0])

    def test_identity_inventory_is_explicitly_historical_and_complete_for_snapshot(self):
        inventory = json.loads((ROOT / "data/geospatial/france-airports-identity-inventory.json").read_text(encoding="utf-8"))
        self.assertEqual(inventory["status"], "historical_identity_inventory_only")
        self.assertEqual(len(inventory["airports"]), 96)
        self.assertEqual(len({entry["icao"] for entry in inventory["airports"]}), 96)

    def test_readiness_audit_covers_every_identity_without_fabricating_packs(self):
        result = audit(ROOT, ROOT / "data/geospatial/france-airports-identity-inventory.json")
        self.assertEqual(result["summary"]["inventoried"], 96)
        self.assertEqual(result["summary"]["context_only"], 96)
        self.assertEqual(result["summary"]["invalid_pack"], 0)
        self.assertEqual(result["summary"]["missing_pack"], 0)
        self.assertEqual(result["operational_claim"], "none")

    def test_registry_validates_all_context_packs(self):
        messages = validate_registry(ROOT / "data/geospatial/france-airports-registry.json")
        self.assertIn("registry: 96 airport pack(s), explicitly partial", messages)

    def test_out_of_bounds_terrain_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            destination_dir = Path(directory) / "data" / "geospatial" / "lfbd"
            destination_dir.mkdir(parents=True)
            for name in ("terrain-grid-mnt2023.json", "buildings.geojson", "source-catalog.json"):
                shutil.copy(ROOT / "data/geospatial/lfbd" / name, destination_dir / name)
            destination = destination_dir / "manifest.json"
            manifest = json.loads((ROOT / "data/geospatial/lfbd/manifest.json").read_text(encoding="utf-8"))
            manifest["bbox"]["north"] = 44.82
            destination.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "outside manifest bbox"):
                validate_manifest(destination, ROOT)


if __name__ == "__main__":
    unittest.main()
