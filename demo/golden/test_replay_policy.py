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
                self.assertTrue(intersection["runway_or_sector"].strip())

    def test_sensor_degradation_does_not_clear_threat(self) -> None:
        degraded = next(risk for risk in self.payloads("cuas.risk.protected_volume") if risk["sensor_coverage_degraded"])
        self.assertNotEqual(degraded["threat_state"], "resolved")
        self.assertIn("sensor_coverage_degraded", degraded["rationale_codes"])

    def test_unknown_cooperative_is_not_treated_as_hostile(self) -> None:
        unknown = next(event for event in self.payloads("operator.timeline") if event["event"] == "unknown_cooperative_uas")
        self.assertEqual(unknown["authorization"], "unknown")
        self.assertEqual(unknown["severity"], "attention")

    def test_operator_authorization_has_named_decision_authority(self) -> None:
        for action in self.payloads("operator.action.authorized"):
            self.assertTrue(action.get("decision_authority", "").strip())

    def test_control_path_uses_versioned_bounded_delegation(self) -> None:
        subjects = [subject for _, subject, _ in EVENTS]
        self.assertIn("furia.s1.mission-delegation", subjects)
        self.assertNotIn("swarm.intent.submit", subjects)
        delegation = self.payloads("furia.s1.mission-delegation")[0]
        self.assertEqual(delegation["schema"], "furia.s1.mission-delegation")
        self.assertEqual(delegation["version"], "1.0.0")
        self.assertGreater(delegation["valid_until_ms"], delegation["dispatched_at_ms"])

    def test_comm_denied_continuation_is_bounded_by_authority_expiry(self) -> None:
        delegation = self.payloads("furia.s1.mission-delegation")[0]
        degraded = self.payloads("s1.execution.degraded")[0]
        self.assertEqual(degraded["continuation"], "bounded_by_contract_expiry")
        self.assertEqual(degraded["authority_valid_until_ms"], delegation["valid_until_ms"])
        expiry_evidence = next(e for e in self.payloads("s1.execution.evidence") if e["rejection_reason"] == "authority_expired")
        self.assertFalse(expiry_evidence["safe_recovery"])

    def test_civilian_conflict_precedes_abort_and_safe_recovery(self) -> None:
        subjects = [subject for _, subject, _ in EVENTS]
        conflict = subjects.index("safety.civilian_aircraft_conflict")
        abort = subjects.index("operator.action.abort")
        safe_evidence = max(i for i, subject in enumerate(subjects) if subject == "s1.execution.evidence")
        self.assertLess(conflict, abort)
        self.assertLess(abort, safe_evidence)
        self.assertTrue(self.payloads("s1.execution.evidence")[-1]["safe_recovery"])

    def test_incident_resolves_without_mitigation_authorized(self) -> None:
        resolved = self.payloads("cuas.incident.state")[-1]
        self.assertEqual(resolved["threat_state"], "resolved")
        self.assertFalse(resolved["mitigation_authorized"])
        self.assertEqual(resolved["recommendation"], "none")


if __name__ == "__main__":
    unittest.main()
