#!/usr/bin/env python3
"""Contract assertions for the deterministic Bordeaux C-UAS replay stimuli.

The replay is an integration driver, not an authority simulator. It may inject
sensor observations, explicit operator authorization, and safety stimuli, but
must never fabricate Core-owned risk/incident decisions or S1 execution output.
Those authoritative outputs are asserted by end-to-end consumers during a live
or recorded run.
"""
from __future__ import annotations

import unittest

from replay import ASTERIX_SUBJECT, EVENTS, MISSION_ID, ROGUE_TRACK_ID


class GoldenReplayContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events = [(subject, payload) for _, subject, payload in EVENTS]

    def payloads(self, subject: str) -> list[dict]:
        return [payload for event_subject, payload in self.events if event_subject == subject]

    def test_replay_drives_real_asterix_ingress(self) -> None:
        records = self.payloads(ASTERIX_SUBJECT)
        self.assertGreaterEqual(len(records), 2)
        self.assertTrue(any(record["category"] == 15 for record in records))
        for record in records:
            self.assertIn("record", record)
            self.assertIsInstance(record["record"], list)

    def test_replay_does_not_fabricate_authoritative_outputs(self) -> None:
        subjects = [subject for subject, _ in self.events]
        forbidden = {
            "cuas.risk.protected_volume",
            "cuas.incident.state",
            "furia.s1.mission-delegation",
            "cuas.execution.evidence",
            "furia.s1.execution-evidence",
            "s1.execution.evidence",
            "swarm.command.abort",
        }
        self.assertTrue(forbidden.isdisjoint(subjects))

    def test_operator_authorization_is_explicit_named_input(self) -> None:
        actions = self.payloads("operator.action.authorized")
        self.assertEqual(len(actions), 1)
        action = actions[0]
        self.assertTrue(action["authorized"])
        self.assertEqual(action["track_id"], ROGUE_TRACK_ID)
        self.assertTrue(action["operator"].strip())
        self.assertTrue(action["authorization_id"].strip())

    def test_replay_never_uses_free_text_direct_s1_intent(self) -> None:
        subjects = [subject for subject, _ in self.events]
        self.assertNotIn("swarm.intent.submit", subjects)
        self.assertNotIn("furia.s1.mission-delegation", subjects)

    def test_civilian_conflict_is_policy_stimulus_for_core_abort(self) -> None:
        conflicts = self.payloads("safety.civilian_aircraft_conflict")
        self.assertEqual(len(conflicts), 1)
        conflict = conflicts[0]
        self.assertEqual(conflict["mission_id"], MISSION_ID)
        self.assertEqual(conflict["track_id"], ROGUE_TRACK_ID)
        self.assertTrue(conflict["flight_id"].strip())
        self.assertTrue(conflict["policy"].strip())

    def test_fresh_kinematic_updates_precede_authorization(self) -> None:
        indexed = list(EVENTS)
        authorization_time = next(at_s for at_s, subject, _ in indexed if subject == "operator.action.authorized")
        cat015_times = [
            at_s
            for at_s, subject, payload in indexed
            if subject == ASTERIX_SUBJECT and payload.get("category") == 15
        ]
        self.assertGreaterEqual(len(cat015_times), 2)
        self.assertTrue(any(at_s < authorization_time for at_s in cat015_times))
        self.assertLess(max(at_s for at_s in cat015_times if at_s < authorization_time), authorization_time)


if __name__ == "__main__":
    unittest.main()
