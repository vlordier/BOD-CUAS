#!/usr/bin/env python3
import json
import unittest
from pathlib import Path

CATALOG = json.loads(Path(__file__).with_name("source-catalog.json").read_text())


class SourceCatalogTest(unittest.TestCase):
    def test_every_source_declares_a_safe_state_and_boundary(self):
        states = {"real_adapter", "training_simulator", "requires_partner"}
        for source in CATALOG["sources"]:
            self.assertIn(source["state"], states)
            self.assertIn(source["authority"], {"context_only", "training_only", "not_connected"})
            self.assertTrue(source["subject"])

    def test_no_partner_feed_is_presented_as_connected(self):
        for source in CATALOG["sources"]:
            if source["state"] == "requires_partner":
                self.assertEqual(source["authority"], "not_connected")


if __name__ == "__main__":
    unittest.main()
