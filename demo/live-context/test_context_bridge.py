#!/usr/bin/env python3
import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).with_name("context_bridge.py")
spec = importlib.util.spec_from_file_location("context_bridge", MODULE)
bridge = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(bridge)


class ContextBridgeTest(unittest.TestCase):
    def test_adsb_is_valid_cat021_crewed_aircraft(self):
        event = bridge.adapt_adsb({"icao24": "ABC123", "latitude": 44.8, "longitude": -0.7, "altitude_m": 100, "ground_speed_mps": 10, "track_deg": 90}, {}, 1000)
        observation = event["observation"]
        self.assertEqual(observation["kind"], "crewed_aircraft")
        self.assertEqual(observation["provenance"]["category"], 21)
        self.assertEqual(observation["cooperative"], True)
        self.assertLessEqual(observation["observed_at_ms"], observation["provenance"]["received_at_ms"])

    def test_remote_id_is_never_authorized_by_receiver(self):
        event = bridge.adapt_remote_id({"id": "RID-1", "latitude": 44.8, "longitude": -0.7, "altitude_m": 100}, {}, 1000)
        observation = event["observation"]
        self.assertEqual(observation["kind"], "cooperative_uas")
        self.assertEqual(observation["provenance"]["category"], 129)
        self.assertIsNone(observation["authorized"])

    def test_weather_extracts_raw_metar_without_interpreting_it(self):
        event = bridge.adapt_weather([{"rawOb": "LFBD 251000Z 24008KT"}], {"airport_icao": "LFBD"}, 1000)
        self.assertEqual(event["raw_metar"], "LFBD 251000Z 24008KT")
        self.assertEqual(event["provenance"], "external_context_unvalidated")

    def test_unknown_source_is_reported_not_raised(self):
        output = bridge.run_source({"id": "bad", "kind": "nope"}, None, Path("."))
        self.assertEqual(output[-1][0], bridge.PROVENANCE_SUBJECT)
        self.assertEqual(output[-1][1]["health"], "degraded")

    def test_receiver_source_always_emits_contract_health(self):
        source = {"id": "adsb", "c2_sensor_id": "ADSB", "kind": "adsb_jsonl", "path": "samples/adsb.jsonl", "sac": 3, "sic": 4}
        output = bridge.run_source(source, None, MODULE.parent)
        health = next(payload for subject, payload in output if subject == "surveillance.sensor.status")
        self.assertEqual(health["sensor_id"], "ADSB")
        self.assertEqual(health["observation"]["provenance"]["category"], 63)
        self.assertEqual(health["connection_status"], "operational")


if __name__ == "__main__":
    unittest.main()
