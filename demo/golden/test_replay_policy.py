#!/usr/bin/env python3
"""Policy-level assertions for the deterministic Bordeaux C-UAS replay."""
from __future__ import annotations

import unittest

from replay import EVENTS


class GoldenReplayPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events = [(subject, payload) for _, subject, payload in EVENTS]

    def payloads(self, subject: str) -> list[dict]:
        return [payload for event_subject, payload in self.events if event_subject == subject]

    def test_risk_horizons_are_standard_and_runway_scoped(self) -> None:
        risks = self.payloads("cuas.risk.protected_volume")
        self.assertGreaterEqual(len(risks), 2)
        for risk in risks:
            for intersection in risk["intersections"]:
                self.assertIn(intersection["horizon_sec"], (30, 60, 120))
                self.assertLessEqual(intersection["predicted_entry_in_ms"], intersection["horizon_sec"] * 1000)
                self.assertTrue(intersection["runway_or_sector"])

    def test_sensor_degradation_does_not_clear_threat(self) -> None:
        risks = self.payloads("cuas.risk.protected_volume")
        degraded = next(risk for risk in risks if risk["sensor_coverage_degraded"])
        self.assertNotEqual(degraded["threat_state"], "resolved")
        self.assertIn("sensor_coverage_degraded", degraded["rationale_codes"])

    def test_operator_authorization_has_named_decision_authority(self) -> None:
        actions = self.payloads("operator.action.authorized")
        self.assertTrue(actions)
        for action in actions:
            self.assertTrue(action.get("decision_authority"))

    def test_cuas_control_path_uses_versioned_delegation_not_free_text_intent(self) -> None:
        subjects = [subject for _, subject, _ in EVENTS]
        self.assertIn("furia.s1.mission-delegation", subjects)
        self.assertNotIn("swarm.intent.submit", subjects)
        delegation = self.payloads("furia.s1.mission-delegation")[0]
        self.assertEqual(delegation["schema"], "furia.s1.mission-delegation")
        self.assertEqual(delegation["version"], "1.0.0")
        self.assertGreater(delegation["plan_revision"], 0)
        self.assertEqual(delegation["authority"]["authorization_id"], "exercise-authority")

    def test_civilian_conflict_precedes_abort_and_safe_recovery(self) -> None:
        subjects = [subject for _, subject, _ in EVENTS]
        conflict = subjects.index("safety.civilian_aircraft_conflict")
        abort = subjects.index("operator.action.abort")
        evidence = subjects.index("s1.execution.evidence")
        self.assertLess(conflict, abort)
        self.assertLess(abort, evidence)
        self.assertTrue(self.payloads("s1.execution.evidence")[-1]["safe_recovery"])

    def test_incident_resolves_without_mitigation_authorized(self) -> None:
        incidents = self.payloads("cuas.incident.state")
        resolved = incidents[-1]
        self.assertEqual(resolved["threat_state"], "resolved")
        self.assertFalse(resolved["mitigation_authorized"])
        self.assertEqual(resolved["recommendation"], "none")

    def test_unknown_cooperative_is_not_treated_as_hostile(self) -> None:
        timelines = self.payloads("operator.timeline")
        unknown = next(event for event in timelines if event["event"] == "unknown_cooperative_uas")
        self.assertEqual(unknown["authorization"], "unknown")
        self.assertEqual(unknown["severity"], "attention")


if __name__ == "__main__":
    unittest.main()
