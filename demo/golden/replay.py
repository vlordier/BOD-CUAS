#!/usr/bin/env python3
"""Deterministic Bordeaux golden-demo event driver using only the NATS wire protocol."""
from __future__ import annotations

import json
import os
import socket
import time
from urllib.parse import urlparse

NATS_URL = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
SPEED = float(os.environ.get("DEMO_SPEED", "1.0"))

EVENTS = [
    (0.0, "scenario.status", {"id": "bod-cuas-golden", "state": "running", "tick": 0, "elapsed_sec": 0}),
    (5.0, "operator.timeline", {"event": "authorized_uas_detected", "track_id": "uas-authorized-01", "authorization": "authorized", "severity": "info"}),
    (10.0, "operator.timeline", {"event": "unknown_cooperative_uas", "track_id": "uas-unknown-01", "authorization": "unknown", "severity": "attention"}),
    (18.0, "operator.timeline", {"event": "known_uas_unauthorized", "track_id": "uas-expired-01", "authorization": "unauthorized", "severity": "high"}),
    (20.0, "operator.timeline", {"event": "rogue_uas_detected", "track_id": "uas-rogue-042", "severity": "high", "sensors": ["radar-low-altitude", "eo-ir"]}),
    (30.0, "cuas.risk.protected_volume", {
        "track_id": "uas-rogue-042",
        "assessed_at_ms": 30_000,
        "threat_state": "credible_threat",
        "confidence_permille": 900,
        "authorization_known": False,
        "authorized": None,
        "sensor_coverage_degraded": False,
        "affected_runways_or_sectors": ["RWY23"],
        "intersections": [{
            "volume_id": "approach-rwy23",
            "runway_or_sector": "RWY23",
            "horizon_sec": 60,
            "predicted_entry_in_ms": 37_000,
            "predicted_exit_in_ms": 52_000,
            "minimum_horizontal_margin_mm": -1_000,
            "minimum_vertical_margin_mm": 2_000,
        }],
        "recommendation": "protect_volume",
        "rationale_codes": ["non_cooperative", "protected_volume_intersection"],
    }),
    (32.0, "surveillance.sensor.status", {"sensor": "radar-low-altitude", "connection_status": "degraded", "coverage_degraded": True}),
    (33.0, "cuas.risk.protected_volume", {
        "track_id": "uas-rogue-042",
        "assessed_at_ms": 33_000,
        "threat_state": "credible_threat",
        "confidence_permille": 700,
        "authorization_known": False,
        "authorized": None,
        "sensor_coverage_degraded": True,
        "affected_runways_or_sectors": ["RWY23"],
        "intersections": [{
            "volume_id": "approach-rwy23",
            "runway_or_sector": "RWY23",
            "horizon_sec": 60,
            "predicted_entry_in_ms": 34_000,
            "predicted_exit_in_ms": 49_000,
            "minimum_horizontal_margin_mm": -1_000,
            "minimum_vertical_margin_mm": 2_000,
        }],
        "recommendation": "protect_volume",
        "rationale_codes": ["protected_volume_intersection", "sensor_coverage_degraded"],
    }),
    (35.0, "swarm.intent.submit", {"scenario_id": "perimeter_defense_fob", "intent": "Monitor, shadow and contain the delegated rogue UAS while preserving runway and civilian-aircraft protected volumes", "authority": "recommend"}),
    (40.0, "cuas.incident.state", {
        "incident_id": "bod-cuas-001",
        "updated_at_ms": 40_000,
        "primary_track_id": "uas-rogue-042",
        "threat_state": "credible_threat",
        "affected_runways_or_sectors": ["RWY23"],
        "recommendation": "restrict_affected_runway_or_sector",
        "operator_acknowledgement_required": True,
        "mitigation_authorized": False,
        "decision_authority": None,
        "audit_reason": "protected-volume risk confirmed",
    }),
    (45.0, "operator.action.authorized", {"action": "bounded_intercept_shadow", "track_id": "uas-rogue-042", "operator": "demo-operator", "decision_authority": "exercise-authority", "authorized": True}),
    (62.0, "operator.timeline", {"event": "second_rogue_uas_detected", "track_id": "uas-rogue-043", "severity": "high"}),
    (70.0, "s1.execution.degraded", {"mode": "degraded_communications", "continuation": "bounded_by_contract_expiry"}),
    (80.0, "safety.civilian_aircraft_conflict", {"flight_id": "AFR762", "track_id": "uas-rogue-042", "policy": "BOD-RWY-FRATRICIDE-003"}),
    (81.0, "operator.action.abort", {"action": "bounded_intercept_shadow", "reason": "civilian_aircraft_conflict", "policy": "BOD-RWY-FRATRICIDE-003"}),
    (88.0, "s1.execution.evidence", {"track_id": "uas-rogue-042", "degraded_mode": "safety_hold", "rejection_reason": "safety_invariant_unavailable", "safe_recovery": True}),
    (95.0, "cuas.incident.state", {
        "incident_id": "bod-cuas-001",
        "updated_at_ms": 95_000,
        "primary_track_id": "uas-rogue-042",
        "threat_state": "resolved",
        "affected_runways_or_sectors": [],
        "recommendation": "none",
        "operator_acknowledgement_required": False,
        "mitigation_authorized": False,
        "decision_authority": None,
        "audit_reason": "safe-recovery-confirmed",
    }),
    (100.0, "scenario.status", {"id": "bod-cuas-golden", "state": "complete", "tick": 100, "elapsed_sec": 100}),
]


def publish(sock: socket.socket, subject: str, payload: dict) -> None:
    data = json.dumps(payload, separators=(",", ":")).encode()
    sock.sendall(f"PUB {subject} {len(data)}\r\n".encode() + data + b"\r\n")


def main() -> None:
    parsed = urlparse(NATS_URL)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 4222
    with socket.create_connection((host, port), timeout=10) as sock:
        sock.settimeout(10)
        _ = sock.recv(4096)  # INFO
        sock.sendall(b'CONNECT {"verbose":false,"pedantic":false,"lang":"python-stdlib","version":"1"}\r\nPING\r\n')
        _ = sock.recv(4096)
        start = time.monotonic()
        for at_s, subject, payload in EVENTS:
            deadline = start + at_s / SPEED
            delay = deadline - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            publish(sock, subject, payload)
            sock.sendall(b"PING\r\n")
            _ = sock.recv(4096)
            print(f"[{at_s:05.1f}s] {subject}: {payload}", flush=True)


if __name__ == "__main__":
    main()
