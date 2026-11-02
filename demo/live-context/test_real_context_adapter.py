import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).with_name("real_context_adapter.py")
spec = importlib.util.spec_from_file_location("real_context_adapter", MODULE)
adapter = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(adapter)


class RealContextAdapterTest(unittest.TestCase):
    def test_opensky_state_vectors_are_context_only_and_normalized(self):
        payload = {"time": 1_700_000_000, "states": [["abc123", " AFR123 ", "France", 0, 1_700_000_000, -0.6, 44.8, 1200, False, 100, 90, 0, None, 1250, None, False, 0]]}
        events = adapter.adapt_opensky(payload, {"id": "opensky", "provider": "OpenSky Network"}, 2_000)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["observation"]["kind"], "crewed_aircraft")
        self.assertTrue(events[0]["observation"]["context_only"])
        self.assertTrue(events[0]["observation"]["cooperative"])
        self.assertEqual(events[0]["observation"]["provenance"]["profile"], "opensky_state_vector_context")

    def test_snapshot_cache_is_used_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            url = "https://example.invalid/context"
            (cache / f"{adapter._cache_key(url)}.json").write_text(json.dumps({"fetched_at_unix": 1, "sha256": "x", "payload": {"ok": True}}))
            payload, meta = adapter.fetch_snapshot(url, cache, no_network=True)
            self.assertEqual(payload, {"ok": True})
            self.assertEqual(meta["mode"], "cache")

    def test_opensky_url_is_bounded_to_lfbd_context_box(self):
        self.assertIn("lamin=44.65", adapter.opensky_url())
        self.assertIn("lomax=-0.35", adapter.opensky_url())


if __name__ == "__main__":
    unittest.main()
