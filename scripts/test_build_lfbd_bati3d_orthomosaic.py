#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_lfbd_bati3d_orthomosaic import mosaic_position, selected_records


class OrthomosaicTest(unittest.TestCase):
    def test_grid_is_north_up(self):
        self.assertEqual(mosaic_position("x64y134", 64, 134, 96), (0, 0))
        self.assertEqual(mosaic_position("x89y110", 64, 134, 96), (25 * 96, 24 * 96))

    def test_incomplete_selection_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "missing x65y110"):
            selected_records(
                [{"id": "x64y110"}], min_x=64, max_x=65, min_y=110, max_y=110
            )


if __name__ == "__main__":
    unittest.main()
