#!/usr/bin/env python3
"""Deterministic Bordeaux golden-demo event driver using only the NATS wire protocol."""
from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from urllib.parse import urlparse

NATS_URL = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
SPEED = float(os.environ.get("DEMO_SPEED", "1.0"))
ASTERIX_SUBJECT = "surveillance.asterix.record"
MISSION_ID = "perimeter_defense_fob"
ROGUE_TRACK_ID = "4660"


def fixtures() -> list[dict]:
    return json.loads(Path(__file__).with_name("asterix_records.json").read_text(encoding="utf-8"))


def ingress_payload(fixture: dict, record: list[int] | None = None) -> dict:
    return {
        "category": fixture["category"],
        "record": list(record if record is not None else fixture["record"]),
        "received_at_ms": 0,
        "altitude_msl_mm": fixture.get("altitude_msl_mm"),
        "ground_elevation_msl_mm": fixture.get("ground_elevation_msl_mm"),
        "_fixture_name": fixture["name"],
    }


def load_asterix_events() -> list[tuple[float, str, dict]]:
    return [(1.0 + i * 0.25, ASTERIX_SUBJECT, ingress_payload(f)) for i, f in enumerate(fixtures())]


def rogue_kinematic_events() -> list[tuple[float, str, dict]]:
    fixture = next(item for item in fixtures() if item["name"] == "non-cooperative-runway-track")
    first = list(fixture["record"])
    second = list(first)
    lat = int.from_bytes(bytes(second[18:22]), "big", signed=True) + 1000
    lon = int.from_bytes(bytes(second[22:26]), "big", signed=True) + 1000
    second[18:22] = lat.to_bytes(4, "big", signed=True)
    second[22:26] = lon.to_bytes(4, "big", signed=True)
    return [(32.0, ASTERIX_SUBJECT, ingress_payload(fixture, first)), (34.0, ASTERIX_SUBJECT, ingress_payload(fixture, second))]


def degraded_sensor_event() -> tuple[float, str, dict]:
    fixture = next(item for item in fixtures() if item["name"] == "degraded-sensor-status")
    return (32.5, ASTERIX_SUBJECT, ingress_payload(fixture))


def origin_evidence_events() -> list[tuple[float, str, dict]]:
    """Synthetic observations only; uncertainty is explicit and simulator truth is never published."""
    base = {"track_id": ROGUE_TRACK_ID, "emitter_id": "RF-12", "observed_at_ms": 0, "acoustic": False}
    bearings = [
        (22.0, {**base, "sensor_id": "RF-01", "sensor_latitude_e7": 448_300_000, "sensor_longitude_e7": -7_500_000, "bearing_mdeg": 101_000, "sigma_mdeg": 4_000}),
        (22.4, {**base, "sensor_id": "RF-02", "sensor_latitude_e7": 448_250_000, "sensor_longitude_e7": -6_900_000, "bearing_mdeg": 286_000, "sigma_mdeg": 5_000}),
        (22.8, {**base, "sensor_id": "RF-03", "sensor_latitude_e7": 448_360_000, "sensor_longitude_e7": -7_100_000, "bearing_mdeg": 204_000, "sigma_mdeg": 6_000}),
        (23.2, {**base, "sensor_id": "MIC-01", "sensor_latitude_e7": 448_315_000, "sensor_longitude_e7": -7_300_000, "bearing_mdeg": 138_000, "sigma_mdeg": 8_000, "acoustic": True}),
        (34.2, {**base, "sensor_id": "RF-01", "sensor_latitude_e7": 448_300_000, "sensor_longitude_e7": -7_500_000, "bearing_mdeg": 102_000, "sigma_mdeg": 4_000}),
    ]
    tdoa_fixes = [
        (24.0, "surveillance.origin.tdoa_fix", {"track_id": ROGUE_TRACK_ID, "emitter_id": "RF-12", "observed_at_ms": 0, "latitude_e7": 448_305_000, "longitude_e7": -7_130_000, "uncertainty_major_mm": 140_000, "uncertainty_minor_mm": 85_000, "uncertainty_bearing_mdeg": 72_000, "confidence_permille": 820, "sensor_ids": ["RF-01", "RF-02", "RF-03"]}),
        (34.6, "surveillance.origin.tdoa_fix", {"track_id": ROGUE_TRACK_ID, "emitter_id": "RF-12", "observed_at_ms": 0, "latitude_e7": 448_307_000, "longitude_e7": -7_127_000, "uncertainty_major_mm": 155_000, "uncertainty_minor_mm": 95_000, "uncertainty_bearing_mdeg": 74_000, "confidence_permille": 790, "sensor_ids": ["RF-01", "RF-02", "RF-03"]}),
    ]
    return [(at, "surveillance.origin.bearing", payload) for at, payload in bearings] + tdoa_fixes


def execution_health_events() -> list[tuple[float, str, dict]]:
    """Simulation facts only. S1 derives Core-facing evidence through the real delegation guard."""
    return [
        (55.0, "s1.sim.execution-health", {"mission_id": MISSION_ID, "comms_available": False, "navigation_safe": True, "authority_valid": True}),
        (65.0, "s1.sim.execution-health", {"mission_id": MISSION_ID, "comms_available": True, "navigation_safe": True, "authority_valid": True}),
    ]


def stamp_cat015_time_of_day(record: list[int], now_ms: int) -> None:
    raw = ((now_ms % 86_400_000) * 128 // 1000) & 0xFFFFFF
    record[6:9] = [(raw >> 16) & 0xFF, (raw >> 8) & 0xFF, raw & 0xFF]


EVENTS = [
    (0.0, "scenario.status", {"id": "bod-cuas-golden", "state": "running", "tick": 0, "elapsed_sec": 0}),
    *load_asterix_events(),
    (20.0, "operator.timeline", {"event": "rogue_uas_detected", "track_id": ROGUE_TRACK_ID, "severity": "high"}),
    *origin_evidence_events(),
    (30.0, "safety.runway_incursion_predicted", {"track_id": ROGUE_TRACK_ID, "runway": "05/23", "eta_s": 37}),
    *rogue_kinematic_events(),
    degraded_sensor_event(),
    (35.0, "operator.action.authorized", {"action": "intercept", "track_id": ROGUE_TRACK_ID, "operator": "demo-operator", "authorization_id": "bod-demo-auth-4660", "authorized": True}),
    *execution_health_events(),
    (80.0, "safety.civilian_aircraft_conflict", {"mission_id": MISSION_ID, "flight_id": "AFR762", "track_id": ROGUE_TRACK_ID, "policy": "BOD-RWY-FRATRICIDE-003"}),
    (95.0, "scenario.status", {"id": "bod-cuas-golden", "state": "complete", "tick": 95, "elapsed_sec": 95}),
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
        _ = sock.recv(4096)
        sock.sendall(b'CONNECT {"verbose":false,"pedantic":false,"lang":"python-stdlib","version":"1"}\r\nPING\r\n')
        _ = sock.recv(4096)
        start = time.monotonic()
        for at_s, subject, source_payload in sorted(EVENTS, key=lambda event: event[0]):
            delay = start + at_s / SPEED - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            payload = dict(source_payload)
            fixture_name = payload.pop("_fixture_name", None)
            now_ms = int(time.time() * 1000)
            if subject == ASTERIX_SUBJECT:
                payload["received_at_ms"] = now_ms
                payload["record"] = list(payload["record"])
                if payload["category"] == 15:
                    stamp_cat015_time_of_day(payload["record"], now_ms)
            elif subject.startswith("surveillance.origin."):
                payload["observed_at_ms"] = now_ms
            elif subject == "s1.sim.execution-health":
                payload["observed_at_ms"] = now_ms
                payload["track_observed_at_ms"] = now_ms
            publish(sock, subject, payload)
            sock.sendall(b"PING\r\n")
            _ = sock.recv(4096)
            label = f" ({fixture_name})" if fixture_name else ""
            print(f"[{at_s:05.2f}s] {subject}{label}: {payload}", flush=True)


if __name__ == "__main__":
    main()
