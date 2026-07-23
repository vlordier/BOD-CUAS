#!/usr/bin/env python3
"""Deterministic Bordeaux golden-demo event driver using only the NATS wire protocol.

This replay injects STIMULI only — never authoritative outputs.
Core owns all authority, delegation, evidence, and safety commands.
"""
from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from urllib.parse import urlparse

NATS_URL = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
SPEED = float(os.environ.get("DEMO_SPEED", "1.0"))

# Subjects
OBSERVATION_SUBJECT = "surveillance.observation"
SCENARIO_STATUS_SUBJECT = "scenario.status"
OPERATOR_AUTHORIZED_SUBJECT = "operator.action.authorized"
S1_EXECUTION_HEALTH_SUBJECT = "s1.sim.execution-health"
SAFETY_CIVILIAN_CONFLICT_SUBJECT = "safety.civilian_aircraft_conflict"


def publish(sock: socket.socket, subject: str, payload: dict) -> None:
    data = json.dumps(payload, separators=(",", ":")).encode()
    sock.sendall(f"PUB {subject} {len(data)}\r\n".encode() + data + b"\r\n")


def make_observation(
    track_id: str,
    kind: str,
    category: int,
    lat_e7: int,
    lon_e7: int,
    alt_mm: int,
    vx: int,
    vy: int,
    vz: int,
    cooperative: bool | None,
    authorized: bool | None,
    observed_at_ms: int,
    received_at_ms: int,
) -> dict:
    return {
        "observation": {
            "kind": kind,
            "observed_at_ms": observed_at_ms,
            "position": {
                "latitude_e7": lat_e7,
                "longitude_e7": lon_e7,
                "altitude_msl_mm": alt_mm,
            },
            "velocity_ned_mm_s": [vx, vy, vz],
            "horizontal_uncertainty_mm": 2000,
            "vertical_uncertainty_mm": 1000,
            "cooperative": cooperative,
            "authorized": authorized,
            "identity": None,
            "provenance": {
                "category": category,
                "edition": "1.0",
                "profile": None,
                "sac": 1,
                "sic": 2,
                "source_track_id": int(track_id),
                "pair_id": None,
                "received_at_ms": received_at_ms,
                "raw_record_sha256": [0] * 32,
            },
        }
    }


def main() -> None:
    parsed = urlparse(NATS_URL)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 4222

    with socket.create_connection((host, port), timeout=10) as sock:
        sock.settimeout(10)
        _ = sock.recv(4096)  # NATS INFO
        sock.sendall(b'CONNECT {"verbose":false,"pedantic":false,"lang":"python-stdlib","version":"1"}\r\nPING\r\n')
        _ = sock.recv(4096)  # PONG

        start = time.monotonic()

        def _publish(subject: str, payload: dict | None) -> None:
            if payload is not None:
                publish(sock, subject, payload)
            sock.sendall(b"PING\r\n")
            _ = sock.recv(4096)

        def emit(at_s: float, subject: str, payload: dict | None = None,
                 *, inject: Callable[[dict], None] | None = None) -> None:
            """Publish at the scheduled time. If `inject` is provided, it is
            called after the sleep with the payload dict, allowing the caller
            to inject fresh timestamps at publication time."""
            deadline = start + at_s / SPEED
            delay = deadline - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            if inject and payload is not None:
                inject(payload)
            _publish(subject, payload)
            print(f"[{at_s:05.2f}s] {subject}", flush=True)

        def emit_with_now(at_s: float, subject: str, payload: dict) -> None:
            """Publish at the scheduled time, injecting fresh timestamps into
            the payload at publication time."""
            def _inject(p: dict) -> None:
                now_ms = int(time.time() * 1000)
                p["observed_at_ms"] = now_ms
                p["track_observed_at_ms"] = now_ms
            emit(at_s, subject, payload, inject=_inject)

        def emit_obs(at_s: float, subject: str, **obs_kw) -> None:
            """Emit an observation with fresh timestamps captured at publication time."""
            def _inject(p: dict) -> None:
                now_ms = int(time.time() * 1000)
                obs_kw["observed_at_ms"] = now_ms
                obs_kw["received_at_ms"] = now_ms
                p.clear()
                p.update({"observation": make_observation(**obs_kw)["observation"]})
            emit(at_s, subject, {}, inject=_inject)

        # 0 s: scenario start
        emit(0.0, SCENARIO_STATUS_SUBJECT, {
            "id": "bod-cuas-golden", "state": "running", "tick": 0, "elapsed_sec": 0,
        })

        # 1 s: CAT129 authorized cooperative UAS (track 7001)
        emit_obs(1.0, OBSERVATION_SUBJECT,
            track_id="7001", kind="cooperative_uas", category=129,
            lat_e7=448400000, lon_e7=-7100000, alt_mm=85000,
            vx=500, vy=0, vz=0, cooperative=True, authorized=True,
        )

        # 2 s: CAT129 unknown cooperative UAS (track 7002)
        emit_obs(2.0, OBSERVATION_SUBJECT,
            track_id="7002", kind="cooperative_uas", category=129,
            lat_e7=448500000, lon_e7=-7200000, alt_mm=90000,
            vx=600, vy=0, vz=0, cooperative=True, authorized=None,
        )

        # 3 s: CAT129 expired/unauthorized UAS (track 7003)
        emit_obs(3.0, OBSERVATION_SUBJECT,
            track_id="7003", kind="cooperative_uas", category=129,
            lat_e7=448300000, lon_e7=-7000000, alt_mm=80000,
            vx=400, vy=0, vz=0, cooperative=True, authorized=False,
        )

        # 4 s: CAT015 non-cooperative runway track (track 4660) — no velocity yet
        emit_obs(4.0, OBSERVATION_SUBJECT,
            track_id="4660", kind="non_cooperative_target", category=15,
            lat_e7=448500000, lon_e7=-7000000, alt_mm=50000,
            vx=0, vy=0, vz=0, cooperative=False, authorized=None,
        )

        # 5 s: CAT063 sensor degraded
        emit(5.0, "surveillance.sensor.status", {
            "observation": make_observation(
                track_id="0", kind="sensor_status", category=63,
                lat_e7=0, lon_e7=0, alt_mm=0,
                vx=0, vy=0, vz=0, cooperative=None, authorized=None,
                observed_at_ms=int(time.time() * 1000),
                received_at_ms=int(time.time() * 1000),
            )["observation"],
            "sensor_sac": 1,
            "sensor_sic": 2,
            "connection_status": "degraded",
        })

        # 10 s: operator timeline event
        emit(10.0, "operator.timeline", {
            "event": "authorized_uas_detected", "track_id": "7001",
            "authorization": "authorized", "severity": "info",
        })

        # 15 s: unknown cooperative UAS
        emit(15.0, "operator.timeline", {
            "event": "unknown_cooperative_uas", "track_id": "7002",
            "authorization": "unknown", "severity": "attention",
        })

        # 20 s: known-but-expired UAS
        emit(20.0, "operator.timeline", {
            "event": "known_uas_unauthorized", "track_id": "7003",
            "authorization": "unauthorized", "severity": "high",
        })

        # 25 s: RF bearing observations — use emit_with_now for fresh timestamps
        emit_with_now(25.0, "surveillance.origin.bearing", {
            "track_id": "4660", "sensor_id": "rf-sensor-01",
            "bearing_cdeg": 31500, "confidence_permille": 800,
            "frequency_mhz": 2400,
        })
        emit_with_now(25.5, "surveillance.origin.bearing", {
            "track_id": "4660", "sensor_id": "rf-sensor-02",
            "bearing_cdeg": 4500, "confidence_permille": 750,
            "frequency_mhz": 2400,
        })
        emit_with_now(26.0, "surveillance.origin.tdoa_fix", {
            "track_id": "4660", "sensor_ids": ["rf-sensor-01", "rf-sensor-02", "rf-sensor-03"],
            "latitude_e7": 448500000, "longitude_e7": -7000000,
            "uncertainty_mm": 200000,
        })

        # 30 s: acoustic corroboration
        emit_with_now(30.0, "surveillance.origin.bearing", {
            "track_id": "4660", "sensor_id": "acoustic-array-01",
            "bearing_cdeg": 32000, "confidence_permille": 600,
            "frequency_mhz": None,
        })

        # 39.5 s: fresh observation with velocity (within track-age window for delegation at 40s)
        emit_obs(39.5, OBSERVATION_SUBJECT,
            track_id="4660", kind="non_cooperative_target", category=15,
            lat_e7=448500000, lon_e7=-7000000, alt_mm=50000,
            vx=1200, vy=-300, vz=0, cooperative=False, authorized=None,
        )

        # 40 s: named operator authorization
        emit(40.0, OPERATOR_AUTHORIZED_SUBJECT, {
            "action": "intercept", "track_id": "4660",
            "operator": "demo-operator",
            "authorization_id": "bod-demo-auth-4660",
            "authorized": True,
        })

        # 50 s: comms loss simulation health injection
        # emit_with_now injects fresh observed_at_ms / track_observed_at_ms at publication time
        emit_with_now(50.0, S1_EXECUTION_HEALTH_SUBJECT, {
            "mission_id": "perimeter_defense_fob",
            "comms_available": False,
            "navigation_safe": True,
            "authority_valid": True,
        })

        # 60 s: comms recovery simulation health injection
        emit_with_now(60.0, S1_EXECUTION_HEALTH_SUBJECT, {
            "mission_id": "perimeter_defense_fob",
            "comms_available": True,
            "navigation_safe": True,
            "authority_valid": True,
        })

        # 70 s: civilian aircraft conflict
        emit(70.0, SAFETY_CIVILIAN_CONFLICT_SUBJECT, {
            "mission_id": "perimeter_defense_fob",
            "flight_id": "AFR762",
            "track_id": "4660",
            "policy": "BOD-RWY-FRATRICIDE-003",
        })

        # 90 s: scenario complete
        emit(90.0, SCENARIO_STATUS_SUBJECT, {
            "id": "bod-cuas-golden", "state": "complete", "tick": 90, "elapsed_sec": 90,
        })

        print("\n=== Replay complete ===", flush=True)


if __name__ == "__main__":
    main()