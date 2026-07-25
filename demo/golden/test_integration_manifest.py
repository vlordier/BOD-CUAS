#!/usr/bin/env python3
"""Tests for local-default and release-pinned integration resolution."""
from __future__ import annotations

import copy
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from resolve_integration_manifest import load_manifest, resolved_repositories


class IntegrationManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_manifest()

    def test_development_refs_are_a_safe_default(self) -> None:
        refs, all_pinned = resolved_repositories(self.manifest)
        self.assertFalse(all_pinned)
        self.assertEqual(refs["furia_c2"], "golden-demo-script")

    def test_release_gate_rejects_unpinned_manifest(self) -> None:
        with self.assertRaisesRegex(ValueError, "release gate"):
            resolved_repositories(self.manifest, require_pins=True)

    def test_release_gate_accepts_immutable_pins(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        pin = "a" * 40
        for repository in manifest["repositories"]:
            repository["pinned_ref"] = pin
        refs, all_pinned = resolved_repositories(manifest, require_pins=True)
        self.assertTrue(all_pinned)
        self.assertEqual(set(refs.values()), {pin})


if __name__ == "__main__":
    unittest.main()
