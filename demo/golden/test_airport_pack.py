import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_airport_pack import validate  # noqa: E402


class AirportPackTests(unittest.TestCase):
    def test_lfbd_pack_is_complete_and_resolves_all_boundaries(self) -> None:
        report = validate(Path(__file__).parent / "airport-packs/lfbd/manifest.json")
        self.assertIn("lfbd-demo-pack: LFBD", report)
        self.assertIn("components=identity,geodata,sensors,sectors,scenarios", report)


if __name__ == "__main__":
    unittest.main()
