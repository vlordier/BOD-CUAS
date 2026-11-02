#!/usr/bin/env python3
"""Unit tests for Bati3D spatial calibration (no multi-GB archive required)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from prepare_lfbd_bati3d import subtile_record


class Bati3DGridTest(unittest.TestCase):
    def test_provider_hk_calibration(self):
        record = subtile_record("HK", "HK/tile_x55y117/tile_x55y117.3ds")
        self.assertEqual(record["epsg3945_bbox"], [1402600, 4187000, 1402800, 4187200])

    def test_texture_is_paired_with_mesh(self):
        record = subtile_record("LK", "LK/tile_x78y120/tile_x78y120.3ds")
        self.assertEqual(record["texture_jpeg"], "LK/tile_x78y120/x78y120.jpg")

    def test_non_mesh_member_is_ignored(self):
        self.assertIsNone(subtile_record("LK", "LK/cartogramme_LK.pdf"))


if __name__ == "__main__":
    unittest.main()
